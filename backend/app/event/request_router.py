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
from app.event.decision_service import request_decision_service
from app.event.models import EventStatus
from app.event.request_schemas import (
    AssignedRequestsOut,
    AssignmentHistoryOut,
    AssignmentWrite,
    CoordinatorOptionsOut,
    EventRequestOut,
    EventRequestWrite,
    EventRequestsOut,
    RequestRejectWrite,
    UnassignedRequestsOut,
)
from app.event.request_service import event_request_service
from app.notification.service import Notifier, get_notifier
from app.user.dependencies import require_user_roles
from app.user.models import User, UserRole

router = APIRouter(prefix="/api/v1/event-requests", tags=["event-requests"])
me_router = APIRouter(prefix="/api/v1/me", tags=["event-requests"])
coordinators_router = APIRouter(prefix="/api/v1/coordinators", tags=["event-requests"])

Organiser = Annotated[User, Depends(require_user_roles(UserRole.ORGANISER))]
Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]
# DECISION-PENDING: D48 — the review queue is the coordinator's (their assigned requests) and the
# Lead's (all of them). Venue Staff read no event requests since SCRUM-120.
Reviewer = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD))]
# Who may open a request and its thread at all; which requests each may open is the service's (D47, D48).
Reader = Annotated[
    User, Depends(require_user_roles(UserRole.ORGANISER, UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD))
]
# Only a Coordinator Lead assigns (SCRUM-13 AC 6).
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
    reviewer: Reviewer,
    db: Session = Depends(get_db),
) -> EventRequestsOut:
    return EventRequestsOut(event_requests=event_request_service.list_for_review(db, reviewer))


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


@router.get("/assigned", response_model=AssignedRequestsOut)
def list_assigned(
    lead: Lead,
    coordinator_id: uuid.UUID | None = None,
    status: EventStatus | None = None,
    db: Session = Depends(get_db),
) -> AssignedRequestsOut:
    return AssignedRequestsOut(event_requests=assignment_service.list_assigned(db, lead, coordinator_id, status))


@coordinators_router.get("", response_model=CoordinatorOptionsOut)
def list_coordinators(
    _: Lead,
    db: Session = Depends(get_db),
) -> CoordinatorOptionsOut:
    return CoordinatorOptionsOut(coordinators=assignment_service.list_coordinators(db))


@router.get("/{request_id}", response_model=EventRequestOut)
def get_request(
    request_id: uuid.UUID,
    reader: Reader,
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


# SCRUM-84 (US17): the assigned coordinator decides a request under review. No body on approve.
@router.post("/{request_id}/approve", response_model=EventRequestOut)
def approve_request(
    request_id: uuid.UUID,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> EventRequestOut:
    return request_decision_service.approve(db, coordinator, request_id, now, notifier)


@router.post("/{request_id}/reject", response_model=EventRequestOut)
def reject_request(
    request_id: uuid.UUID,
    body: RequestRejectWrite,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> EventRequestOut:
    return request_decision_service.reject(db, coordinator, request_id, body, now, notifier)


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
    reader: Reader,
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
