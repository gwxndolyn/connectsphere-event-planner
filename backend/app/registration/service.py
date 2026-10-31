import logging
import uuid
from collections.abc import Iterable
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
    MyExpiredRegistrationOut,
    MyOfferedRegistrationOut,
    MyRegistrationOut,
    MyRegistrationsResponse,
    MyWaitlistedRegistrationOut,
    OfferReleaseResponse,
    RegisterResponse,
    WaitlistJoinResponse,
    WithdrawResponse,
)
from app.user.models import Attendee
from app.venue.models import Venue
from app.venue.primary import attendee_venue, primary_venues

logger = logging.getLogger(__name__)

WITHDRAWABLE_STATUSES = (RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLISTED)

# TC-X-01: timestamps are stored UTC; the team and every event are Asia/Singapore. "My
# Registrations" is the first endpoint that renders wall-clock date/time strings rather than
# an ISO instant, so it's the one place that has to pick a display timezone.
EVENT_TIMEZONE = ZoneInfo("Asia/Singapore")

# D1, decided (SCRUM-137): an offer is held for 24 hours. One constant, one edit if that changes.
WAITLIST_OFFER_WINDOW = timedelta(hours=24)


def _lock_event(db: Session, event_id: uuid.UUID) -> Event | None:
    """Lock the event row for the rest of the transaction, so a concurrent registration, withdrawal or
    expiry can't read a stale seat count (spec §2, Concurrency). Every change to an event's seats takes it."""
    return db.scalars(select(Event).where(Event.id == event_id).with_for_update()).one_or_none()


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

    def waitlist_available(self, db: Session, event: Event, now: datetime) -> bool:
        """US6a AC 1/2 (SCRUM-48): the event is full, an unexpired offer counting as taken, and
        waitlists are enabled for it. Short-circuits, so a disabled event never counts seats."""
        return event.waitlist_enabled and self.seats_remaining(db, event, now) <= 0

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
        # DECISION-PENDING: D17 — not gated on waitlist_enabled. US6a only governs joining, so
        # people already queued keep their place if the event's waitlist is switched off later.
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
                registration_id=next_in_line.id,
            )
        except Exception:
            # The withdrawal and the offer still stand; only the message failed (TC-US7-15).
            logger.exception("could not notify %s of a waitlist offer", next_in_line.attendee_email)

        return next_in_line

    def _end_offer(
        self,
        db: Session,
        event: Event,
        registration: Registration,
        new_status: RegistrationStatus,
        action: str,
        now: datetime,
    ) -> None:
        """The one way an offer ends (decline, expiry): the new status and a log row. The caller holds
        the event lock and passes the seat on."""
        registration.status = new_status
        registration.updated_at = now
        if new_status == RegistrationStatus.EXPIRED and registration.offer_expires_at is not None:
            # A forced early expiry (`/expire-offer`) records when the offer really ended (TC-US7-22).
            registration.offer_expires_at = min(registration.offer_expires_at, now)
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

    def expire_lapsed_offers(
        self, db: Session, event_ids: Iterable[uuid.UUID], now: datetime, notifier: Notifier
    ) -> int:
        """D2, decided (SCRUM-137): lapse on read, no scheduler. Every read or change of an event's
        registrations calls this first, so an offer past `offer_expires_at` expires and its place
        passes to the next person in line (notified, with a new window) or back to capacity.

        The pattern, for anything else that lapses (US25's tentative holds should copy it):
        1. A cheap check without a lock. The usual answer is "nothing lapsed": no lock, no write.
        2. Each event found, in id order, in its own transaction: lock it, re-check under the lock
           (another request may have swept it already), apply the change, commit. One event lock at
           a time, in a fixed order, so two board reads can't deadlock (TC-US7-19, TC-US7-24).
        3. It commits on its own, before the caller's work, so a refusal that follows (EVENT_FULL,
           OFFER_EXPIRED) can't roll the hand-over back (TC-US7-17, TC-US7-20).

        Returns how many offers it expired."""
        ids = list(event_ids)
        if not ids:
            return 0
        lapsed_event_ids = db.scalars(
            select(Registration.event_id)
            .where(
                Registration.event_id.in_(ids),
                Registration.status == RegistrationStatus.OFFERED,
                Registration.offer_expires_at <= now,
            )
            .distinct()
        ).all()

        expired = 0
        for event_id in sorted(lapsed_event_ids):
            event = _lock_event(db, event_id)
            # Re-read under the lock. populate_existing, so a row this session already holds shows
            # another request's committed sweep rather than a stale copy.
            lapsed = db.scalars(
                select(Registration)
                .where(
                    Registration.event_id == event_id,
                    Registration.status == RegistrationStatus.OFFERED,
                    Registration.offer_expires_at <= now,
                )
                .order_by(Registration.offer_expires_at, Registration.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
            if event is not None and lapsed:
                for registration in lapsed:
                    self._end_offer(db, event, registration, RegistrationStatus.EXPIRED, "offer_expired", now)
                expired += len(lapsed)
                # Once the event is on, the place goes to no one: accept would refuse them with
                # EVENT_STARTED, and a "you have 24 hours" notice would be wrong (TC-US7-23).
                if now < event.start_at:
                    while self.offer_freed_seat(db, event, now, notifier) is not None:
                        pass
            db.commit()
        return expired

    def _refuse_lapsed_offer(self, registration: Registration, now: datetime) -> None:
        """Accept and decline: an offer that has expired, whether the sweep just did it or an earlier
        read did, is OFFER_EXPIRED, so the holder hears one thing however they arrive (deviation 13)."""
        if registration.status == RegistrationStatus.EXPIRED or (
            registration.status == RegistrationStatus.OFFERED
            and (registration.offer_expires_at is None or registration.offer_expires_at <= now)
        ):
            raise DomainError(409, "OFFER_EXPIRED")

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

        if new_status == RegistrationStatus.DECLINED:
            # Declining reads the event's registrations, so lapsed offers expire first (D2).
            # `/expire-offer` is the forced test path and ends its offer whatever the time.
            self.expire_lapsed_offers(db, [registration.event_id], now, notifier)

        event = _lock_event(db, registration.event_id)
        db.refresh(registration, with_for_update=True)

        if new_status == RegistrationStatus.DECLINED:
            self._refuse_lapsed_offer(registration, now)
        if registration.status != RegistrationStatus.OFFERED:
            raise DomainError(409, "NO_ACTIVE_OFFER")

        self._end_offer(db, event, registration, new_status, action, now)

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
        """SCRUM-37, kept for tests: a forced expiry. Real expiry is `expire_lapsed_offers`, on read
        (D2, SCRUM-137). It doesn't check that offer_expires_at has passed, and isn't restricted to
        the offer holder, so a test can end an offer at any time (deviation 4)."""
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

    def accept_offer(
        self, db: Session, registration_id: uuid.UUID, attendee: Attendee, now: datetime, notifier: Notifier
    ) -> RegisterResponse:
        """The offer holder takes up the seat (SCRUM-51, US6b AC 2): offered → confirmed.
        Anyone not holding a live offer is refused and keeps their status (AC 3)."""
        registration = db.get(Registration, registration_id)
        # Email-only waitlist entries from before SCRUM-136 (D3) have no attendee to match, so they
        # 404 here too, until their attendee tries to join and join_waitlist links them.
        if registration is None or registration.attendee_id != attendee.id:
            raise DomainError(404, "NOT_FOUND")

        # A lapsed offer no longer holds its seat: expire it and pass the place on first (D2), so the
        # refusal below doesn't leave the next person waiting (TC-US7-17).
        self.expire_lapsed_offers(db, [registration.event_id], now, notifier)
        event = _lock_event(db, registration.event_id)
        db.refresh(registration, with_for_update=True)

        self._refuse_lapsed_offer(registration, now)
        if registration.status != RegistrationStatus.OFFERED:
            raise DomainError(409, "NO_ACTIVE_OFFER")
        if now >= event.start_at:
            raise DomainError(403, "EVENT_STARTED")

        registration.status = RegistrationStatus.CONFIRMED
        registration.offer_expires_at = None
        registration.updated_at = now
        db.add(
            AttendanceLog(
                registration_id=registration.id,
                event_id=event.id,
                attendee_id=attendee.id,
                action="registered",
                occurred_at=now,
                note="accepted waitlist offer",
            )
        )
        db.flush()
        response = self._confirmation(db, registration, event)
        db.commit()
        return response

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

        self.expire_lapsed_offers(db, [registration.event_id], now, notifier)
        # Lock the event, then re-read the registration under lock in case it changed while we waited.
        event = _lock_event(db, registration.event_id)
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
        notifier: Notifier,
    ) -> RegisterResponse:
        """SCRUM-26: TC-US3-02 … TC-US3-10, TC-US3-15."""
        # A lapsed offer's seat goes to the waitlist first, not to this newcomer (D2, TC-US7-20).
        self.expire_lapsed_offers(db, [event_id], now, notifier)
        # Lock the event row for the rest of the transaction so two attendees racing for the
        # last seat can't both read the same occupancy (spec §2 Concurrency, TC-US3-10).
        event = _lock_event(db, event_id)
        if event is None:
            raise DomainError(404, "NOT_FOUND")

        self._check_registration_open(event, now)

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
            # second, explicit POST /waitlist call is required. Only offered when the event
            # supports one (US6a AC 1, 2).
            waitlist_available = self.waitlist_available(db, event, now)
            raise DomainError(
                409,
                "EVENT_FULL",
                waitlist_available=waitlist_available,
                message="This event is full. You may join the waitlist."
                if waitlist_available
                else "This event is full.",
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

        return self._confirmation(db, registration, event)

    def _check_registration_open(self, event: Event, now: datetime) -> None:
        """The two gates (spec §2): a confirmed event with registration enabled, inside its window."""
        if event.status != EventStatus.CONFIRMED or not event.registration_enabled:
            raise DomainError(403, "REGISTRATION_NOT_ENABLED")
        if event.registration_opens_at is not None and now < event.registration_opens_at:
            raise DomainError(403, "REGISTRATION_CLOSED")
        if event.registration_closes_at is not None and now >= event.registration_closes_at:
            raise DomainError(403, "REGISTRATION_CLOSED")

    def _confirmation(self, db: Session, registration: Registration, event: Event) -> RegisterResponse:
        # US24 (D70): the event's approved primary venue, else its own venue_name.
        venue_name, _ = attendee_venue(event, primary_venues(db, [event.id]).get(event.id))
        return RegisterResponse(
            registration_id=registration.id,
            status=registration.status,
            event=EventConfirmationOut(
                name=event.name,
                start_at=event.start_at,
                end_at=event.end_at,
                venue_name=venue_name,
                join_link=event.join_link,
            ),
        )

    def join_waitlist(
        self, db: Session, event_id: uuid.UUID, attendee: Attendee, now: datetime, notifier: Notifier
    ) -> WaitlistJoinResponse:
        """SCRUM-27: TC-US3-11 … TC-US3-14. The explicit follow-up to an `EVENT_FULL` offer.
        SCRUM-49: refused unless that offer would have been made (US6a AC 1, 2).
        SCRUM-136: the logged-in attendee joins, so every new place has an attendee (D3, D7 settled)."""
        self.expire_lapsed_offers(db, [event_id], now, notifier)
        event = _lock_event(db, event_id)
        if event is None:
            raise DomainError(404, "NOT_FOUND")
        # DECISION-PENDING: D16 — US6a doesn't say, but "reached its registration capacity"
        # presumes registration is open, so the waitlist takes register's gates.
        self._check_registration_open(event, now)

        already = db.scalars(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.attendee_id == attendee.id,
                Registration.status.in_(ACTIVE_STATUSES),
            )
        ).first()
        if already is not None:
            raise DomainError(409, "ALREADY_REGISTERED")
        # A place joined by email before SCRUM-136 has no attendee, so it couldn't accept an offer.
        # It's theirs: link it, keep its place in the queue, and say they're already on it. It kept the
        # email as typed, so match it in any letter case, as logins match users (PR #106 review).
        email_only = db.scalars(
            select(Registration).where(
                Registration.event_id == event_id,
                Registration.attendee_id.is_(None),
                func.lower(Registration.attendee_email) == attendee.email.lower(),
                Registration.status.in_(ACTIVE_STATUSES),
            )
        ).first()
        if email_only is not None:
            email_only.attendee_id = attendee.id
            email_only.updated_at = now
            db.commit()
            raise DomainError(409, "ALREADY_REGISTERED")

        if not self.waitlist_available(db, event, now):
            # A disabled waitlist wins: nothing will ever be offered there. Otherwise there are
            # places left, and the attendee should register instead (deviation 16).
            code = "WAITLIST_NOT_ENABLED" if not event.waitlist_enabled else "SEATS_AVAILABLE"
            raise DomainError(409, code)

        # D3: both, always. `attendee_id` links the row to "My Events" (SCRUM-5) and lets it accept
        # an offer; `attendee_email` is the attendee's own, never a typed one (SCRUM-136).
        registration = Registration(
            event_id=event.id,
            attendee_id=attendee.id,
            attendee_email=attendee.email,
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

    def _my_registration_fields(
        self, registration: Registration, event: Event, venue: Venue | None = None
    ) -> dict[str, object]:
        local_start = event.start_at.astimezone(EVENT_TIMEZONE)
        local_end = event.end_at.astimezone(EVENT_TIMEZONE)
        # US24 (D70): an in-person event's primary venue and its location, else venue_name / room_number.
        venue_name, location = attendee_venue(event, venue)
        joining_info = event.join_link if event.delivery_mode == DeliveryMode.ONLINE else location
        return {
            "registration_id": registration.id,
            "event_id": event.id,
            "event_name": event.name,
            "date": local_start.date().isoformat(),
            "start_time": local_start.strftime("%H:%M"),
            "end_time": local_end.strftime("%H:%M"),
            "venue_name": venue_name,
            "joining_info": joining_info or "",
            "delivery_mode": event.delivery_mode,
        }

    def list_my_registrations(
        self, db: Session, attendee: Attendee, now: datetime, notifier: Notifier
    ) -> MyRegistrationsResponse:
        """SCRUM-30 (query by attendee, split confirmed/waitlisted), SCRUM-31 (sort ascending
        by start, alphabetical tiebreak). TC-US11-01 … 11.

        Filtered on `end_at`, not `start_at` (TC-US11-09) — an in-progress event still shows.
        `withdrawn`/`declined`/`expired` rows never show, so withdrawing drops a row from here for
        free (TC-US11-08). A live offer gets its own `offered` section (SCRUM-50): it's the
        on-screen notice that a place is waiting (D5), and the attendee accepts from there.

        SCRUM-137: lapsed offers on the attendee's events expire first (D2), so a place passed to them
        shows here at once, and an offer of theirs that lapsed shows under `expired` (TC-US7-22).
        """
        self.expire_lapsed_offers(
            db,
            db.scalars(
                select(Registration.event_id)
                .join(Event, Event.id == Registration.event_id)
                .where(
                    Registration.attendee_id == attendee.id,
                    Registration.status.in_(ACTIVE_STATUSES),
                    Event.end_at > now,
                )
                .distinct()
            ).all(),
            now,
            notifier,
        )
        rows = db.execute(
            select(Registration, Event)
            .join(Event, Event.id == Registration.event_id)
            .where(
                Registration.attendee_id == attendee.id,
                or_(
                    Registration.status.in_((RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLISTED)),
                    # A lapsed offer can't be accepted (OFFER_EXPIRED), so it isn't offered any more.
                    and_(
                        Registration.status == RegistrationStatus.OFFERED,
                        Registration.offer_expires_at > now,
                    ),
                ),
                Event.end_at > now,
            )
            .order_by(Event.start_at, Event.name)
        ).all()

        confirmed: list[MyRegistrationOut] = []
        waitlisted: list[MyWaitlistedRegistrationOut] = []
        offered: list[MyOfferedRegistrationOut] = []
        venues = primary_venues(db, {event.id for _, event in rows})
        for registration, event in rows:
            fields = self._my_registration_fields(registration, event, venues.get(event.id))
            if registration.status == RegistrationStatus.CONFIRMED:
                confirmed.append(MyRegistrationOut(**fields))
            elif registration.status == RegistrationStatus.OFFERED:
                offered.append(MyOfferedRegistrationOut(**fields, offer_expires_at=registration.offer_expires_at))
            else:
                waitlisted.append(
                    MyWaitlistedRegistrationOut(
                        **fields, waitlist_position=self.waitlist_position(db, registration)
                    )
                )

        # Offers that lapsed, on events still to come, unless the attendee is back on the event with
        # an active row (they rejoined the queue): the screen shouldn't say both.
        active_event_ids = {event.id for _, event in rows}
        lapsed = db.execute(
            select(Registration, Event)
            .join(Event, Event.id == Registration.event_id)
            .where(
                Registration.attendee_id == attendee.id,
                Registration.status == RegistrationStatus.EXPIRED,
                Registration.offer_expires_at.is_not(None),
                Event.end_at > now,
            )
            .order_by(Event.start_at, Event.name)
        ).all()
        lapsed = [(registration, event) for registration, event in lapsed if event.id not in active_event_ids]
        venues.update(primary_venues(db, {event.id for _, event in lapsed} - set(venues)))
        expired = [
            MyExpiredRegistrationOut(
                **self._my_registration_fields(registration, event, venues.get(event.id)),
                offer_expires_at=registration.offer_expires_at,
            )
            for registration, event in lapsed
        ]
        return MyRegistrationsResponse(confirmed=confirmed, waitlisted=waitlisted, offered=offered, expired=expired)


registration_service = RegistrationService()
