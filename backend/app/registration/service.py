import logging
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import DeliveryMode, Event, EventRegistrationField, EventStatus
from app.notification.service import Notifier
from app.registration.models import (
    ACTIVE_STATUSES,
    AttendanceLog,
    Registration,
    RegistrationAnswer,
    RegistrationStatus,
)
from app.registration.schemas import (
    EventConfirmationOut,
    MyRegistrationOut,
    MyRegistrationsResponse,
    MyWaitlistedRegistrationOut,
    OfferReleaseResponse,
    RegisterResponse,
    WaitlistJoinResponse,
    WithdrawResponse,
)
from app.user.models import Attendee

logger = logging.getLogger(__name__)

WITHDRAWABLE_STATUSES = (RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLISTED)

# TC-X-01: timestamps are stored UTC; the team and every event are Asia/Singapore. "My
# Registrations" is the first endpoint that renders wall-clock date/time strings rather than
# an ISO instant, so it's the one place that has to pick a display timezone.
EVENT_TIMEZONE = ZoneInfo("Asia/Singapore")

# DECISION-PENDING: D1 — SCRUM-6 says "a fixed window to accept" and names no duration.
# One constant, one edit when the team decides.
WAITLIST_OFFER_WINDOW = timedelta(hours=24)


class RegistrationService:
    def seats_remaining(self, db: Session, event: Event, now: datetime) -> int:
        """Capacity minus occupancy, computed on read (TC-X-02). An unexpired offer holds its seat."""
        occupancy = db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.event_id == event.id,
                or_(
                    Registration.status == RegistrationStatus.CONFIRMED,
                    and_(
                        Registration.status == RegistrationStatus.OFFERED,
                        Registration.offer_expires_at > now,
                    ),
                ),
            )
        )
        return event.capacity - (occupancy or 0)

    def waitlist_position(self, db: Session, registration: Registration) -> int | None:
        """1-based rank among the event's waitlisted rows. Derived from join time, never stored.
        `id` breaks ties so two rows sharing a timestamp still get distinct, stable positions."""
        if registration.status != RegistrationStatus.WAITLISTED:
            return None
        return db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.event_id == registration.event_id,
                Registration.status == RegistrationStatus.WAITLISTED,
                tuple_(Registration.waitlist_joined_at, Registration.id)
                <= (registration.waitlist_joined_at, registration.id),
            )
        )

    def _head_of_waitlist(self, db: Session, event: Event) -> Registration | None:
        """Oldest waitlisted row for this event, locked so two withdrawals can't offer the
        same seat to the same person."""
        return db.scalars(
            select(Registration)
            .where(
                Registration.event_id == event.id,
                Registration.status == RegistrationStatus.WAITLISTED,
            )
            .order_by(Registration.waitlist_joined_at, Registration.id)
            .limit(1)
            .with_for_update()
        ).first()

    def offer_freed_seat(
        self, db: Session, event: Event, now: datetime, notifier: Notifier
    ) -> Registration | None:
        """Hand a free seat to the head of the waitlist (SCRUM-36). The offer holds the seat
        until it expires, so seats_remaining does not rise (TC-US7-07, TC-US7-09)."""
        if self.seats_remaining(db, event, now) <= 0:
            return None
        next_in_line = self._head_of_waitlist(db, event)
        if next_in_line is None:
            # No waitlist: the seat simply returns to the pool, and nobody is notified (TC-US7-06).
            return None

        next_in_line.status = RegistrationStatus.OFFERED
        next_in_line.offer_expires_at = now + WAITLIST_OFFER_WINDOW
        next_in_line.updated_at = now
        db.add(
            AttendanceLog(
                registration_id=next_in_line.id,
                event_id=event.id,
                attendee_id=next_in_line.attendee_id,
                action="offered",
                occurred_at=now,
                note=f"offer expires {next_in_line.offer_expires_at.isoformat()}",
            )
        )
        db.flush()

        try:
            notifier.waitlist_offer(
                email=next_in_line.attendee_email,
                event_name=event.name,
                expires_at=next_in_line.offer_expires_at,
            )
        except Exception:
            # The withdrawal and the offer still stand; only the message failed (TC-US7-15).
            logger.exception("could not notify %s of a waitlist offer", next_in_line.attendee_email)

        return next_in_line

    def _release_offer(
        self,
        db: Session,
        registration_id: uuid.UUID,
        new_status: RegistrationStatus,
        action: str,
        now: datetime,
        notifier: Notifier,
        attendee: Attendee | None = None,
    ) -> OfferReleaseResponse:
        """Shared by expiry and decline: end an outstanding offer, then pass the seat on."""
        registration = db.get(Registration, registration_id)
        if registration is None or (attendee is not None and registration.attendee_id != attendee.id):
            raise DomainError(404, "NOT_FOUND")

        event = db.scalars(select(Event).where(Event.id == registration.event_id).with_for_update()).one()
        db.refresh(registration, with_for_update=True)

        if registration.status != RegistrationStatus.OFFERED:
            raise DomainError(409, "NO_ACTIVE_OFFER")

        registration.status = new_status
        registration.updated_at = now
        db.add(
            AttendanceLog(
                registration_id=registration.id,
                event_id=event.id,
                attendee_id=registration.attendee_id,
                action=action,
                occurred_at=now,
            )
        )
        db.flush()

        # The seat is free again: straight to the next person, no waiting (TC-US7-10, 11).
        passed_on = self.offer_freed_seat(db, event, now, notifier) is not None

        response = OfferReleaseResponse(
            status=registration.status,
            event_name=event.name,
            seats_remaining=self.seats_remaining(db, event, now),
            offer_passed_on=passed_on,
        )
        db.commit()
        return response

    def expire_offer(
        self, db: Session, registration_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> OfferReleaseResponse:
        """SCRUM-37, manual stub for the scheduled sweep the team hasn't specified yet.

        # DECISION-PENDING: D2 — replace with a scheduled sweep once the team agrees on the
        # offer window. It deliberately does not check that offer_expires_at has passed, and
        # it isn't restricted to the offer holder, because it stands in for a system job.
        """
        return self._release_offer(
            db, registration_id, RegistrationStatus.EXPIRED, "offer_expired", now, notifier
        )

    def decline_offer(
        self,
        db: Session,
        registration_id: uuid.UUID,
        attendee: Attendee,
        now: datetime,
        notifier: Notifier,
    ) -> OfferReleaseResponse:
        """The offer holder turns the seat down, so it moves on immediately (TC-US7-11)."""
        return self._release_offer(
            db,
            registration_id,
            RegistrationStatus.DECLINED,
            "declined",
            now,
            notifier,
            attendee=attendee,
        )

    def withdraw(
        self,
        db: Session,
        registration_id: uuid.UUID,
        attendee: Attendee,
        now: datetime,
        notifier: Notifier,
    ) -> WithdrawResponse:
        registration = db.get(Registration, registration_id)
        # 404 rather than 403, so the response doesn't reveal that another attendee's
        # registration exists (TC-US7-02, TC-X-04).
        if registration is None or registration.attendee_id != attendee.id:
            raise DomainError(404, "NOT_FOUND")

        # Lock the event row for the rest of the transaction so a concurrent registration or
        # withdrawal can't read a stale seat count (spec §2, Concurrency). Then re-read the
        # registration under lock in case it changed while we waited.
        event = db.scalars(select(Event).where(Event.id == registration.event_id).with_for_update()).one()
        db.refresh(registration, with_for_update=True)

        if registration.status == RegistrationStatus.WITHDRAWN:
            raise DomainError(409, "ALREADY_WITHDRAWN")
        if registration.status not in WITHDRAWABLE_STATUSES:
            # Not in the spec's error table. An `offered` seat is released by declining it
            # (SCRUM-37); declined/expired rows hold nothing to withdraw from.
            raise DomainError(409, "REGISTRATION_NOT_ACTIVE")
        # The cutoff is start_at itself: anything strictly before it is allowed (TC-US7-04).
        if now >= event.start_at:
            raise DomainError(403, "EVENT_STARTED")

        freed_a_seat = registration.status == RegistrationStatus.CONFIRMED
        registration.status = RegistrationStatus.WITHDRAWN
        registration.withdrawn_at = now
        registration.updated_at = now
        db.add(
            AttendanceLog(
                registration_id=registration.id,
                event_id=event.id,
                attendee_id=attendee.id,
                action="withdrawn",
                occurred_at=now,
            )
        )
        db.flush()

        # Leaving a waitlist frees nothing — everyone behind simply moves up (TC-US7-14).
        if freed_a_seat:
            self.offer_freed_seat(db, event, now, notifier)

        response = WithdrawResponse(
            status=registration.status,
            withdrawn_at=now,
            event_name=event.name,
            seats_remaining=self.seats_remaining(db, event, now),
        )
        db.commit()
        return response

    def register(
        self,
        db: Session,
        event_id: uuid.UUID,
        attendee: Attendee,
        answers: dict[str, str],
        now: datetime,
    ) -> RegisterResponse:
        """SCRUM-26: TC-US3-02 … TC-US3-10, TC-US3-15."""
        # Lock the event row for the rest of the transaction so two attendees racing for the
        # last seat can't both read the same occupancy (spec §2 Concurrency, TC-US3-10).
        event = db.scalars(select(Event).where(Event.id == event_id).with_for_update()).one_or_none()
        if event is None:
            raise DomainError(404, "NOT_FOUND")

        if event.status != EventStatus.CONFIRMED or not event.registration_enabled:
            raise DomainError(403, "REGISTRATION_NOT_ENABLED")
        if event.registration_opens_at is not None and now < event.registration_opens_at:
            raise DomainError(403, "REGISTRATION_CLOSED")
        if event.registration_closes_at is not None and now >= event.registration_closes_at:
            raise DomainError(403, "REGISTRATION_CLOSED")

        fields = db.scalars(
            select(EventRegistrationField).where(EventRegistrationField.event_id == event_id)
        ).all()
        missing = [f.field_key for f in fields if f.required and not answers.get(f.field_key)]
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)

        already = db.scalars(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.attendee_id == attendee.id,
                Registration.status.in_(ACTIVE_STATUSES),
            )
        ).first()
        if already is not None:
            raise DomainError(409, "ALREADY_REGISTERED")

        if self.seats_remaining(db, event, now) <= 0:
            # AC: the attendee is *offered* a waitlist place, not silently joined to it — a
            # second, explicit POST /waitlist call is required.
            raise DomainError(
                409,
                "EVENT_FULL",
                waitlist_available=True,
                message="This event is full. You may join the waitlist.",
            )

        registration = Registration(
            event_id=event.id,
            attendee_id=attendee.id,
            attendee_email=attendee.email,
            status=RegistrationStatus.CONFIRMED,
            registered_at=now,
            updated_at=now,
        )
        db.add(registration)
        try:
            db.flush()
        except IntegrityError:
            # Belt-and-braces for TC-US3-09: the partial unique index catches a duplicate
            # even if two identical requests raced past the check above.
            db.rollback()
            raise DomainError(409, "ALREADY_REGISTERED") from None

        for field_key, value in answers.items():
            db.add(RegistrationAnswer(registration_id=registration.id, field_key=field_key, value=value))
        db.add(
            AttendanceLog(
                registration_id=registration.id,
                event_id=event.id,
                attendee_id=attendee.id,
                action="registered",
                occurred_at=now,
            )
        )
        db.commit()

        return RegisterResponse(
            registration_id=registration.id,
            status=registration.status,
            event=EventConfirmationOut(
                name=event.name,
                start_at=event.start_at,
                end_at=event.end_at,
                venue_name=event.venue_name,
                join_link=event.join_link,
            ),
        )

    def join_waitlist(
        self, db: Session, event_id: uuid.UUID, email: str, now: datetime
    ) -> WaitlistJoinResponse:
        """SCRUM-27: TC-US3-11 … TC-US3-14. The explicit follow-up to an `EVENT_FULL` offer.

        # DECISION-PENDING: D7 — §3's identity paragraph says every endpoint depends on
        # get_current_attendee, but this endpoint's own contract is body-only (`{"email": ...}`),
        # matching SCRUM-2's AC ("offered to be put on a waitlist using their email") and D3's
        # email-only case. Sprint 1 default: no X-Attendee-Id required here; `attendee_id` is
        # still attached below when an Attendee row matches the email, so it still surfaces in
        # "My Events" (SCRUM-5) once that attendee does authenticate elsewhere.
        """
        event = db.scalars(select(Event).where(Event.id == event_id).with_for_update()).one_or_none()
        if event is None:
            raise DomainError(404, "NOT_FOUND")

        already = db.scalars(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.attendee_email == email,
                Registration.status.in_(ACTIVE_STATUSES),
            )
        ).first()
        if already is not None:
            raise DomainError(409, "ALREADY_REGISTERED")

        # D3: store both when we can. `attendee_id` links the row to "My Events" (SCRUM-5);
        # `attendee_email` is always set, since the AC only promises an email for the waitlist.
        attendee = db.scalars(select(Attendee).where(Attendee.email == email)).first()

        registration = Registration(
            event_id=event.id,
            attendee_id=attendee.id if attendee else None,
            attendee_email=email,
            status=RegistrationStatus.WAITLISTED,
            waitlist_joined_at=now,
            updated_at=now,
        )
        db.add(registration)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise DomainError(409, "ALREADY_REGISTERED") from None

        db.add(
            AttendanceLog(
                registration_id=registration.id,
                event_id=event.id,
                attendee_id=registration.attendee_id,
                action="waitlisted",
                occurred_at=now,
            )
        )
        db.commit()

        return WaitlistJoinResponse(
            registration_id=registration.id,
            status=registration.status,
            position=self.waitlist_position(db, registration),
        )

    def _my_registration_fields(self, registration: Registration, event: Event) -> dict[str, object]:
        local_start = event.start_at.astimezone(EVENT_TIMEZONE)
        local_end = event.end_at.astimezone(EVENT_TIMEZONE)
        joining_info = event.join_link if event.delivery_mode == DeliveryMode.ONLINE else event.room_number
        return {
            "registration_id": registration.id,
            "event_name": event.name,
            "date": local_start.date().isoformat(),
            "start_time": local_start.strftime("%H:%M"),
            "end_time": local_end.strftime("%H:%M"),
            "venue_name": event.venue_name,
            "joining_info": joining_info or "",
            "delivery_mode": event.delivery_mode,
        }

    def list_my_registrations(
        self, db: Session, attendee: Attendee, now: datetime
    ) -> MyRegistrationsResponse:
        """SCRUM-30 (query by attendee, split confirmed/waitlisted), SCRUM-31 (sort ascending
        by start, alphabetical tiebreak). TC-US11-01 … 11.

        Filtered on `end_at`, not `start_at` (TC-US11-09) — an in-progress event still shows.
        Only `confirmed` and `waitlisted` rows: `offered`/`withdrawn`/`declined`/`expired` aren't
        "registered for" in the AC's sense, and withdrawing already drops a row from here for
        free (TC-US11-08) since `withdrawn` isn't in that set.
        """
        rows = db.execute(
            select(Registration, Event)
            .join(Event, Event.id == Registration.event_id)
            .where(
                Registration.attendee_id == attendee.id,
                Registration.status.in_((RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLISTED)),
                Event.end_at > now,
            )
            .order_by(Event.start_at, Event.name)
        ).all()

        confirmed: list[MyRegistrationOut] = []
        waitlisted: list[MyWaitlistedRegistrationOut] = []
        for registration, event in rows:
            fields = self._my_registration_fields(registration, event)
            if registration.status == RegistrationStatus.CONFIRMED:
                confirmed.append(MyRegistrationOut(**fields))
            else:
                waitlisted.append(
                    MyWaitlistedRegistrationOut(
                        **fields, waitlist_position=self.waitlist_position(db, registration)
                    )
                )
        return MyRegistrationsResponse(confirmed=confirmed, waitlisted=waitlisted)


registration_service = RegistrationService()
