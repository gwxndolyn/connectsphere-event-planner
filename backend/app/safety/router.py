import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.notification.service import Notifier, get_notifier
from app.safety.schemas import (
    SafetyQueueOut,
    SafetyReviewDetailOut,
    SafetyReviewInternalOut,
    SafetyReviewWrite,
    SafetyStatusOut,
)
from app.safety.service import safety_service
from app.user.dependencies import require_user_roles
from app.user.models import User, UserRole

# The Safety Officer's own routes (US30a).
router = APIRouter(prefix="/api/v1/safety-reviews", tags=["safety"])
# What the Coordinator and Organiser do with an event's safety review hangs off the event request.
requests_router = APIRouter(prefix="/api/v1/event-requests", tags=["safety"])

SafetyOfficer = Annotated[User, Depends(require_user_roles(UserRole.SAFETY_OFFICER))]
Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]
# Who may open a request at all; which requests each may open is the request service's (D47, D48).
Reader = Annotated[
    User, Depends(require_user_roles(UserRole.ORGANISER, UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD))
]


@router.get("", response_model=SafetyQueueOut)
def queue(_: SafetyOfficer, db: Session = Depends(get_db), now: datetime = Depends(get_now)) -> SafetyQueueOut:
    return safety_service.queue(db, now)


@router.get("/{event_id}", response_model=SafetyReviewDetailOut)
def detail(
    event_id: uuid.UUID, _: SafetyOfficer, db: Session = Depends(get_db), now: datetime = Depends(get_now)
) -> SafetyReviewDetailOut:
    return safety_service.detail(db, event_id, now)


@router.post("/{event_id}", status_code=201, response_model=SafetyReviewInternalOut)
def review(
    event_id: uuid.UUID,
    body: SafetyReviewWrite,
    officer: SafetyOfficer,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> SafetyReviewInternalOut:
    return safety_service.review(db, officer, event_id, body, now, notifier)


@requests_router.get("/{request_id}/safety-reviews", response_model=SafetyStatusOut)
def safety_status(request_id: uuid.UUID, reader: Reader, db: Session = Depends(get_db)) -> SafetyStatusOut:
    return safety_service.status(db, request_id, reader)


@requests_router.post("/{request_id}/safety-review-request", response_model=SafetyStatusOut)
def request_another_review(
    request_id: uuid.UUID,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> SafetyStatusOut:
    return safety_service.request_review(db, coordinator, request_id, now)
