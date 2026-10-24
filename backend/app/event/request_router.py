import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.event.clarification_schemas import (
    ClarificationRequestWrite,
    ClarificationResponseWrite,
    ClarificationSentOut,
    ClarificationThreadOut,
)
from app.event.clarification_service import clarification_service
from app.event.assignment_service import assignment_service
from app.event.request_schemas import (
    AssignmentHistoryOut,
    AssignmentWrite,
    CoordinatorOptionsOut,
    EventRequestOut,
    EventRequestWrite,
    EventRequestsOut,
    UnassignedRequestsOut,
)
from app.event.request_service import event_request_service
from app.notification.service import Notifier, get_notifier
from app.user.dependencies import get_current_user, require_user_roles
from app.user.models import User, UserRole

router = APIRouter(prefix="/api/v1/event-requests", tags=["event-requests"])
me_router = APIRouter(prefix="/api/v1/me", tags=["event-requests"])
coordinators_router = APIRouter(prefix="/api/v1/coordinators", tags=["event-requests"])

Organiser = Annotated[User, Depends(require_user_roles(UserRole.ORGANISER))]
Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]
Staff = Annotated[
    User,
    Depends(require_user_roles(UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD, UserRole.OPERATIONS_MANAGER)),
]
# DECISION-PENDING: SCRUM-82 owns role checks; until it lands, the seeded `coordinator_lead` role is
# the only one that assigns (SCRUM-13 AC 6).
Lead = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR_LEAD))]


@router.post("", status_code=201, response_model=EventRequestOut)
def create_draft(
    body: EventRequestWrite,
    organiser: Organiser,
    db: Session = Depends(get_db),
) -> EventRequestOut:
    return event_request_service.create_draft(db, organiser, body)


@router.get("", response_model=EventRequestsOut)
def list_for_review(
    _: Staff,
    db: Session = Depends(get_db),
) -> EventRequestsOut:
    return EventRequestsOut(event_requests=event_request_service.list_for_review(db))


@me_router.get("/event-requests", response_model=EventRequestsOut)
def list_my_requests(
    organiser: Organiser,
    db: Session = Depends(get_db),
) -> EventRequestsOut:
    return EventRequestsOut(event_requests=event_request_service.list_mine(db, organiser))


# Registered before `/{request_id}` so "unassigned" is not read as an id.
@router.get("/unassigned", response_model=UnassignedRequestsOut)
def list_unassigned(
    _: Lead,
    db: Session = Depends(get_db),
) -> UnassignedRequestsOut:
    return UnassignedRequestsOut(event_requests=assignment_service.list_unassigned(db))


@coordinators_router.get("", response_model=CoordinatorOptionsOut)
def list_coordinators(
    _: Lead,
    db: Session = Depends(get_db),
) -> CoordinatorOptionsOut:
    return CoordinatorOptionsOut(coordinators=assignment_service.list_coordinators(db))


@router.get("/{request_id}", response_model=EventRequestOut)
def get_request(
    request_id: uuid.UUID,
    reader: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventRequestOut:
    return event_request_service.get(db, request_id, reader)


@router.patch("/{request_id}", response_model=EventRequestOut)
def update_draft(
    request_id: uuid.UUID,
    body: EventRequestWrite,
    organiser: Organiser,
    db: Session = Depends(get_db),
) -> EventRequestOut:
    return event_request_service.update_draft(db, request_id, organiser, body)


@router.post("/{request_id}/submit", response_model=EventRequestOut)
def submit_request(
    request_id: uuid.UUID,
    organiser: Organiser,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> EventRequestOut:
    return event_request_service.submit(db, request_id, organiser, now, notifier)

@router.get("/{request_id}/assignment-history", response_model=AssignmentHistoryOut)
def assignment_history(
    request_id: uuid.UUID,
    _: Lead,
    db: Session = Depends(get_db),
) -> AssignmentHistoryOut:
    return AssignmentHistoryOut(assignments=assignment_service.history(db, request_id))


@router.post("/{request_id}/assignment", response_model=EventRequestOut)
def assign_coordinator(
    request_id: uuid.UUID,
    body: AssignmentWrite,
    lead: Lead,
    db: Session = Depends(get_db),
    notifier: Notifier = Depends(get_notifier),
) -> EventRequestOut:
    return assignment_service.assign(db, request_id, lead, body.coordinator_id, notifier)


@router.post("/{request_id}/clarifications", status_code=201, response_model=ClarificationSentOut)
def send_clarification(
    request_id: uuid.UUID,
    body: ClarificationRequestWrite,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> ClarificationSentOut:
    return clarification_service.send_request(db, request_id, coordinator, body, now, notifier)


@router.get("/{request_id}/clarifications", response_model=ClarificationThreadOut)
def read_clarification_thread(
    request_id: uuid.UUID,
    reader: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClarificationThreadOut:
    return ClarificationThreadOut(clarifications=clarification_service.read_thread(db, request_id, reader))


@router.post("/{request_id}/clarifications/response", status_code=201, response_model=ClarificationSentOut)
def respond_to_clarification(
    request_id: uuid.UUID,
    body: ClarificationResponseWrite,
    organiser: Organiser,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ClarificationSentOut:
    return clarification_service.send_response(db, request_id, organiser, body, now)
