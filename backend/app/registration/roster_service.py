import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event, EventRegistrationField, EventStatus
from app.event.schemas import RegistrationFieldOut
from app.registration.models import Registration, RegistrationAnswer, RegistrationStatus
from app.registration.schemas import (
    EventRegistrantOut,
    EventRegistrationsResponse,
    ManagedEventOut,
    RegistrationTotalsOut,
)
from app.registration.service import registration_service
from app.user.models import User, UserRole

# Past the request stage, so the row is an event that can take registrations. A request (draft to
# rejected) has none, and D11 keeps staff out of drafts.
MANAGED_EVENT_STATUSES = (
    EventStatus.PLANNING,
    EventStatus.CONFIRMED,
    EventStatus.CANCELLED,
    EventStatus.COMPLETED,
)

# US28 AC 5: left out unless the caller asks for them ("Show all") or filters on them.
HIDDEN_BY_DEFAULT = (RegistrationStatus.WITHDRAWN, RegistrationStatus.DECLINED, RegistrationStatus.EXPIRED)

# Seat holders first, then the queue in order, then the inactive rows.
STATUS_ORDER = {
    status: index
    for index, status in enumerate(
        (
            RegistrationStatus.CONFIRMED,
            RegistrationStatus.OFFERED,
            RegistrationStatus.WAITLISTED,
            RegistrationStatus.WITHDRAWN,
            RegistrationStatus.DECLINED,
            RegistrationStatus.EXPIRED,
        )
    )
}


class RegistrationRosterService:
    """US28 (SCRUM-96): an Organiser or Coordinator sees who registered for an event they manage."""

    def _manages(self, event: Event, user: User) -> bool:
        if user.role == UserRole.ORGANISER:
            return event.created_by_user_id == user.id
        # DECISION-PENDING: D27 — events have no assigned coordinator until US10a (SCRUM-13), so any
        # active coordinator manages every event, as D14 and D20 assume. US10a narrows it here.
        return user.role == UserRole.COORDINATOR

    def list_managed_events(self, db: Session, user: User) -> list[ManagedEventOut]:
        query = select(Event).where(Event.status.in_(MANAGED_EVENT_STATUSES))
        if user.role == UserRole.ORGANISER:
            query = query.where(Event.created_by_user_id == user.id)
        events = db.scalars(query.order_by(Event.start_at, Event.id)).all()
        return [ManagedEventOut.model_validate(event, from_attributes=True) for event in events]

    def list_registrations(
        self,
        db: Session,
        event_id: uuid.UUID,
        user: User,
        now: datetime,
        statuses: list[RegistrationStatus] | None = None,
        show_all: bool = False,
    ) -> EventRegistrationsResponse:
        """Totals over every registration (AC 2); the list narrowed to `statuses` when given (AC 4),
        else to active rows unless `show_all` (AC 5). Someone else's event is 404 (AC 1, §1a)."""
        event = db.get(Event, event_id)
        if event is None or event.status not in MANAGED_EVENT_STATUSES or not self._manages(event, user):
            raise DomainError(404, "NOT_FOUND")

        rows = db.execute(
            select(Registration, User.full_name)
            .outerjoin(User, User.id == Registration.attendee_id)
            .where(Registration.event_id == event.id)
        ).all()

        # Position is derived from join order, never stored (§2), so rank the queue here once.
        queue = sorted(
            (registration for registration, _ in rows if registration.status == RegistrationStatus.WAITLISTED),
            key=lambda registration: (registration.waitlist_joined_at, registration.id),
        )
        positions = {registration.id: index for index, registration in enumerate(queue, start=1)}

        def counted(status: RegistrationStatus) -> int:
            return sum(1 for registration, _ in rows if registration.status == status)

        totals = RegistrationTotalsOut(
            confirmed=counted(RegistrationStatus.CONFIRMED),
            waitlisted=counted(RegistrationStatus.WAITLISTED),
            offered=counted(RegistrationStatus.OFFERED),
            seats_remaining=max(registration_service.seats_remaining(db, event, now), 0),
        )

        if statuses:
            shown = [row for row in rows if row[0].status in statuses]
        elif show_all:
            shown = list(rows)
        else:
            shown = [row for row in rows if row[0].status not in HIDDEN_BY_DEFAULT]
        shown.sort(
            key=lambda row: (
                STATUS_ORDER[row[0].status],
                positions.get(row[0].id, 0),
                row[0].registered_at,
                row[0].id,
            )
        )

        answers: dict[uuid.UUID, dict[str, str | None]] = {}
        if shown:
            for answer in db.scalars(
                select(RegistrationAnswer).where(
                    RegistrationAnswer.registration_id.in_([registration.id for registration, _ in shown])
                )
            ):
                answers.setdefault(answer.registration_id, {})[answer.field_key] = answer.value

        fields = db.scalars(
            select(EventRegistrationField)
            .where(EventRegistrationField.event_id == event.id)
            .order_by(EventRegistrationField.sort_order, EventRegistrationField.field_key)
        ).all()

        return EventRegistrationsResponse(
            event=ManagedEventOut.model_validate(event, from_attributes=True),
            totals=totals,
            registration_fields=[
                RegistrationFieldOut.model_validate(field, from_attributes=True) for field in fields
            ],
            registrations=[
                EventRegistrantOut(
                    registration_id=registration.id,
                    attendee_name=full_name,
                    attendee_email=registration.attendee_email,
                    status=registration.status,
                    registered_at=registration.registered_at,
                    waitlist_position=positions.get(registration.id),
                    offer_expires_at=(
                        registration.offer_expires_at
                        if registration.status == RegistrationStatus.OFFERED
                        else None
                    ),
                    answers=answers.get(registration.id, {}),
                )
                for registration, full_name in shown
            ],
        )


registration_roster_service = RegistrationRosterService()
