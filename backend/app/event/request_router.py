import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.event.clarification_schemas import ClarificationRequestWrite, ClarificationSentOut
from app.event.clarification_service import clarification_service
from app.event.request_schemas import EventRequestOut, EventRequestWrite, EventRequestsOut
from app.event.request_service import event_request_service
from app.user.dependencies import get_current_user, require_user_roles
from app.user.models import User, UserRole

router = APIRouter(prefix="/api/v1/event-requests", tags=["event-requests"])
me_router = APIRouter(prefix="/api/v1/me", tags=["event-requests"])

Organiser = Annotated[User, Depends(require_user_roles(UserRole.ORGANISER))]
Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]
Staff = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR, UserRole.OPERATIONS_MANAGER))]


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
) -> EventRequestOut:
    return event_request_service.submit(db, request_id, organiser, now)

@router.post("/{request_id}/clarifications", status_code=201, response_model=ClarificationSentOut)
def send_clarification(
    request_id: uuid.UUID,
    body: ClarificationRequestWrite,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ClarificationSentOut:
    return clarification_service.send_request(db, request_id, coordinator, body, now)
