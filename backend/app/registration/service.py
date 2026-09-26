import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event
from app.notification.service import Notifier
from app.registration.models import AttendanceLog, Registration, RegistrationStatus
from app.registration.schemas import WithdrawResponse
from app.user.models import Attendee

logger = logging.getLogger(__name__)

WITHDRAWABLE_STATUSES = (RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLISTED)

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


registration_service = RegistrationService()
