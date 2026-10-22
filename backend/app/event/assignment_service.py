import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event, EventStatus
from app.event.request_schemas import (
    CoordinatorOptionOut,
    EventRequestOut,
    UnassignedRequestOut,
)
from app.user.models import User, UserRole


class AssignmentService:
    """SCRUM-13 (US10a): the Event Coordinator Lead gives a submitted request one coordinator."""

    def list_unassigned(self, db: Session) -> list[UnassignedRequestOut]:
        """Submitted requests nobody owns yet, oldest first (AC 1). Assigned requests leave it (AC 5)."""
        events = db.scalars(
            select(Event)
            .where(Event.status == EventStatus.SUBMITTED, Event.coordinator_id.is_(None))
            .order_by(Event.submitted_at, Event.id)
        ).all()
        return [UnassignedRequestOut.model_validate(event) for event in events]

    def list_coordinators(self, db: Session) -> list[CoordinatorOptionOut]:
        """Who the Lead may pick: active users with the coordinator role (AC 4)."""
        users = db.scalars(
            select(User)
            .where(User.role == UserRole.COORDINATOR, User.is_active.is_(True))
            .order_by(User.full_name, User.email)
        ).all()
        return [CoordinatorOptionOut.model_validate(user) for user in users]

    def assign(
        self, db: Session, request_id: uuid.UUID, lead: User, coordinator_id: uuid.UUID
    ) -> EventRequestOut:
        event = db.scalars(select(Event).where(Event.id == request_id).with_for_update()).one_or_none()
        # Drafts and finished events are invisible to staff (D11), so they 404, not 409.
        if event is None or event.status in NOT_A_REQUEST_STATUSES:
            raise DomainError(404, "NOT_FOUND")
        if event.status != EventStatus.SUBMITTED or event.coordinator_id is not None:
            raise DomainError(409, "ASSIGNMENT_NOT_ALLOWED", status=event.status.value)

        coordinator = self._eligible_coordinator(db, lead, coordinator_id)
        event.coordinator = coordinator
        # DECISION-PENDING: D27 — assignment starts the review (Under Review), not Planning as
        # SCRUM-61's wording says: Planning comes after approval (SCRUM-84) and hides the request
        # from coordinators under D11.
        event.status = EventStatus.UNDER_REVIEW

        db.flush()
        result = EventRequestOut.model_validate(event)
        db.commit()
        return result

    def _eligible_coordinator(self, db: Session, lead: User, coordinator_id: uuid.UUID) -> User:
        """AC 4 and 7: say why a pick is refused; the caller changes nothing when this raises."""
        if coordinator_id == lead.id:
            raise DomainError(422, "INVALID_COORDINATOR", reason="self_assignment")
        coordinator = db.get(User, coordinator_id)
        if coordinator is None:
            raise DomainError(422, "INVALID_COORDINATOR", reason="unknown_user")
        if coordinator.role != UserRole.COORDINATOR:
            raise DomainError(422, "INVALID_COORDINATOR", reason="not_a_coordinator")
        if not coordinator.is_active:
            raise DomainError(422, "INVALID_COORDINATOR", reason="inactive")
        return coordinator


NOT_A_REQUEST_STATUSES = (
    EventStatus.DRAFT,
    EventStatus.PLANNING,
    EventStatus.CONFIRMED,
    EventStatus.CANCELLED,
    EventStatus.COMPLETED,
)

assignment_service = AssignmentService()
