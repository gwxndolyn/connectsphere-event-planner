import logging
import uuid
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import DomainError
from app.event.models import AssignmentKind, CoordinatorAssignment, Event, EventStatus
from app.event.request_schemas import (
    AssignedRequestOut,
    AssignmentRecordOut,
    CoordinatorOptionOut,
    EventRequestOut,
    UnassignedRequestOut,
)
from app.notification.service import AssignmentRecipient, Notifier
from app.user.models import User, UserRole

logger = logging.getLogger(__name__)

# D30: what "events currently planning" counts in the picker (SCRUM-67). Literally "Planning status"
# would stay at 0 after an assignment, because an assigned request is Under Review (D27) until
# approval, so it counts every status a coordinator is actively working an event through.
WORKLOAD_STATUSES = (
    EventStatus.UNDER_REVIEW,
    EventStatus.AWAITING_CLARIFICATION,
    EventStatus.APPROVED,
    EventStatus.PLANNING,
)

# SCRUM-86 (D44, DECISION-PENDING): "active" events on the Lead's Assigned tab: owned by a coordinator and not yet over.
ACTIVE_ASSIGNED_STATUSES = (
    EventStatus.UNDER_REVIEW,
    EventStatus.AWAITING_CLARIFICATION,
    EventStatus.APPROVED,
    EventStatus.PLANNING,
    EventStatus.CONFIRMED,
)
EVENT_TIMEZONE = ZoneInfo("Asia/Singapore")

# What a notice says when a request has no reference or name (the screens say the same).
MISSING_REFERENCE = "no reference yet"
MISSING_NAME = "Untitled event request"


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

    def list_assigned(
        self,
        db: Session,
        lead: User,
        coordinator_id: uuid.UUID | None = None,
        status: EventStatus | None = None,
    ) -> list[AssignedRequestOut]:
        """The active events this Lead assigned, optionally for one coordinator and/or one status
        (SCRUM-86 AC 2, 3). The Lead's scope is the assigner on an event's latest assignment record
        (D44), so each Lead sees their own and none is hard-coded (AC 6). Soonest event date first,
        undated last."""
        if status is not None and status not in ACTIVE_ASSIGNED_STATUSES:
            raise DomainError(422, "INVALID_STATUS_FILTER", status=status.value)
        latest = (
            select(CoordinatorAssignment.event_id, CoordinatorAssignment.assigned_by_user_id)
            .distinct(CoordinatorAssignment.event_id)
            .order_by(
                CoordinatorAssignment.event_id,
                CoordinatorAssignment.created_at.desc(),
                CoordinatorAssignment.id.desc(),
            )
            .subquery()
        )
        query = (
            select(Event)
            .join(latest, latest.c.event_id == Event.id)
            .where(
                latest.c.assigned_by_user_id == lead.id,
                Event.coordinator_id.is_not(None),
                Event.status.in_([status] if status else ACTIVE_ASSIGNED_STATUSES),
            )
        )
        if coordinator_id is not None:
            query = query.where(Event.coordinator_id == coordinator_id)
        rows = []
        for event in db.scalars(query).all():
            if event.start_at is not None:
                event_date = event.start_at.astimezone(EVENT_TIMEZONE).date()
            else:
                event_date = event.preferred_dates[0] if event.preferred_dates else None
            rows.append(AssignedRequestOut.model_validate(event).model_copy(update={"event_date": event_date}))
        rows.sort(key=lambda row: (row.event_date is None, row.event_date or date.min, row.name or "", str(row.id)))
        return rows

    def list_coordinators(self, db: Session) -> list[CoordinatorOptionOut]:
        """Who the Lead may pick: active users with the coordinator role (SCRUM-13 AC 4), each with
        the number of events they are currently planning, 0 when none (SCRUM-67 AC 1, 2, D30)."""
        rows = db.execute(
            select(User, func.count(Event.id))
            .outerjoin(
                Event,
                and_(Event.coordinator_id == User.id, Event.status.in_(WORKLOAD_STATUSES)),
            )
            .where(User.roles.any(UserRole.COORDINATOR), User.is_active.is_(True))
            .group_by(User.id)
            .order_by(User.full_name, User.email)
        ).all()
        return [
            CoordinatorOptionOut.model_validate(
                {"id": user.id, "display_name": user.display_name, "email": user.email, "planning_count": count}
            )
            for user, count in rows
        ]

    def history(self, db: Session, request_id: uuid.UUID) -> list[AssignmentRecordOut]:
        """An event's Assignment History, newest first (SCRUM-69 AC 2). A draft has no owner to
        account for and is invisible to staff (D11), so it 404s like an unknown id."""
        event = db.get(Event, request_id)
        if event is None or event.status == EventStatus.DRAFT:
            raise DomainError(404, "NOT_FOUND")
        records = db.scalars(
            select(CoordinatorAssignment)
            .where(CoordinatorAssignment.event_id == request_id)
            .options(selectinload(CoordinatorAssignment.assigned_by), selectinload(CoordinatorAssignment.coordinator))
            .order_by(CoordinatorAssignment.created_at.desc(), CoordinatorAssignment.id.desc())
        ).all()
        return [AssignmentRecordOut.model_validate(record) for record in records]

    def assign(
        self,
        db: Session,
        request_id: uuid.UUID,
        lead: User,
        coordinator_id: uuid.UUID,
        notifier: Notifier,
    ) -> EventRequestOut:
        event = db.scalars(select(Event).where(Event.id == request_id).with_for_update()).one_or_none()
        # Drafts and finished events are invisible to staff (D11), so they 404, not 409.
        if event is None or event.status in NOT_A_REQUEST_STATUSES:
            raise DomainError(404, "NOT_FOUND")
        if event.status != EventStatus.SUBMITTED or event.coordinator_id is not None:
            raise DomainError(409, "ASSIGNMENT_NOT_ALLOWED", status=event.status.value)

        coordinator = self._eligible_coordinator(db, lead, coordinator_id)
        event.coordinator = coordinator
        # SCRUM-69 AC 1: the record commits or rolls back with the assignment itself.
        db.add(
            CoordinatorAssignment(
                event_id=event.id,
                assigned_by_user_id=lead.id,
                coordinator_id=coordinator.id,
                kind=AssignmentKind.ASSIGNMENT,
            )
        )
        # DECISION-PENDING: D27 — assignment starts the review (Under Review), not Planning as
        # SCRUM-61's wording says: Planning comes after approval (SCRUM-84) and hides the request
        # from coordinators under D11.
        event.status = EventStatus.UNDER_REVIEW

        db.flush()
        result = EventRequestOut.model_validate(event)
        notice = (
            event.request_reference,
            event.name,
            coordinator.display_name,
            list(event.preferred_dates or []),
        )
        coordinator_email = coordinator.email
        organiser_id = event.created_by_user_id
        db.commit()

        self._notify(db, request_id, notifier, coordinator_email, organiser_id, *notice)
        return result

    def _notify(
        self,
        db: Session,
        request_id: uuid.UUID,
        notifier: Notifier,
        coordinator_email: str,
        organiser_id: uuid.UUID | None,
        request_reference: str | None,
        event_name: str | None,
        coordinator_name: str,
        event_dates: list[date],
    ) -> None:
        """SCRUM-68 (US10c) AC 1 and 2: the new coordinator and the organiser each get a notice
        naming the event, the coordinator and the event date. The request has no confirmed date yet,
        so the date is its preferred dates (D29). Sent only after the assignment commits, so a
        refused one tells no one (AC 3). Best effort like the other notices: a failure is logged,
        never undoes the assignment, and one recipient failing doesn't stop the other."""
        # A submitted request always has both, but if one is ever missing the people are still told,
        # with a stand-in label, rather than hearing nothing about their assignment.
        if not request_reference or not event_name:
            logger.warning("assignment notices for request %s are missing request details", request_id)
        request_reference = request_reference or MISSING_REFERENCE
        event_name = event_name or MISSING_NAME

        recipients: list[tuple[AssignmentRecipient, str]] = [("coordinator", coordinator_email)]
        try:
            organiser = db.get(User, organiser_id) if organiser_id else None
        except Exception:
            logger.exception("could not look up the organiser of request %s", request_id)
            organiser = None
        if organiser is None or not organiser.email:
            logger.warning("could not notify the organiser of request %s: no owner or email", request_id)
        else:
            recipients.append(("organiser", organiser.email))

        for recipient, email in recipients:
            try:
                notifier.assignment_made(
                    email=email,
                    recipient=recipient,
                    request_reference=request_reference,
                    event_name=event_name,
                    coordinator_name=coordinator_name,
                    event_dates=event_dates,
                )
            except Exception:
                logger.exception("could not send the %s assignment notice for request %s", recipient, request_id)

    def _eligible_coordinator(self, db: Session, lead: User, coordinator_id: uuid.UUID) -> User:
        """AC 4 and 7: say why a pick is refused; the caller changes nothing when this raises."""
        if coordinator_id == lead.id:
            raise DomainError(422, "INVALID_COORDINATOR", reason="self_assignment")
        coordinator = db.get(User, coordinator_id)
        if coordinator is None:
            raise DomainError(422, "INVALID_COORDINATOR", reason="unknown_user")
        if not coordinator.holds(UserRole.COORDINATOR):
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
