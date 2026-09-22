import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event
from app.registration.models import AttendanceLog, Registration, RegistrationStatus
from app.registration.schemas import WithdrawResponse
from app.user.models import Attendee

WITHDRAWABLE_STATUSES = (RegistrationStatus.CONFIRMED, RegistrationStatus.WAITLISTED)


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
        """1-based rank by waitlist_joined_at among the event's waitlisted rows. Derived, never stored."""
        if registration.status != RegistrationStatus.WAITLISTED:
            return None
        return db.scalar(
            select(func.count())
            .select_from(Registration)
            .where(
                Registration.event_id == registration.event_id,
                Registration.status == RegistrationStatus.WAITLISTED,
                Registration.waitlist_joined_at <= registration.waitlist_joined_at,
            )
        )

    def withdraw(
        self, db: Session, registration_id: uuid.UUID, attendee: Attendee, now: datetime
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
        # TODO(SCRUM-36): when this frees a confirmed seat and the waitlist isn't empty, offer the
        # seat to the head of the queue instead of returning it to the pool (TC-US7-07..09).
        db.flush()

        response = WithdrawResponse(
            status=registration.status,
            withdrawn_at=now,
            event_name=event.name,
            seats_remaining=self.seats_remaining(db, event, now),
        )
        db.commit()
        return response


registration_service = RegistrationService()
