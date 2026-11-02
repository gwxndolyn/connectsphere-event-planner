import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.event.change_decision_schemas import (
    ChangeDecisionOut,
    ChangeRequestReviewOut,
    ChangeRequestReviewsOut,
    ClearFlagWrite,
    RejectionWrite,
    ReviewFlagOut,
    ReviewFlagsOut,
)
from app.event.change_decision_service import change_decision_service
from app.event.review_flag_service import review_flag_service
from app.notification.service import Notifier, get_notifier
from app.user.dependencies import require_user_roles
from app.user.models import User, UserRole

# US29b (SCRUM-142): change requests, decided by the event's coordinator or, for a coordinator's own US12 edit, a
# Lead (D102). The Lead's screen is Coordinator edits to approve on the Assignment Queue (SCRUM-144).
router = APIRouter(prefix="/api/v1/change-requests", tags=["change-requests"])
# The review flags a significant approval raises (D104), for the event's coordinator.
events_router = APIRouter(prefix="/api/v1/events", tags=["change-requests"])
flags_router = APIRouter(prefix="/api/v1/review-flags", tags=["change-requests"])

Decider = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD))]
Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]


@router.get("", response_model=ChangeRequestReviewsOut)
def list_change_requests(
    user: Decider,
    status: Literal["pending_approval", "decided", "all"] = "pending_approval",
    event_id: uuid.UUID | None = None,
    # Calvin's #127 review: the frontend's acting role, so a user holding both sees one role's requests at a time.
    acting_as: Literal["coordinator", "coordinator_lead"] | None = None,
    db: Session = Depends(get_db),
) -> ChangeRequestReviewsOut:
    role = UserRole(acting_as) if acting_as else None
    return ChangeRequestReviewsOut(change_requests=change_decision_service.list_for(db, user, status, event_id, role))


@router.get("/{request_id}", response_model=ChangeRequestReviewOut)
def get_change_request(request_id: uuid.UUID, user: Decider, db: Session = Depends(get_db)) -> ChangeRequestReviewOut:
    return change_decision_service.get(db, user, request_id)


@router.post("/{request_id}/approve", response_model=ChangeDecisionOut)
def approve_change_request(
    request_id: uuid.UUID,
    user: Decider,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> ChangeDecisionOut:
    return change_decision_service.approve(db, user, request_id, now, notifier)


@router.post("/{request_id}/reject", response_model=ChangeDecisionOut)
def reject_change_request(
    request_id: uuid.UUID,
    body: RejectionWrite,
    user: Decider,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> ChangeDecisionOut:
    return change_decision_service.reject(db, user, request_id, body.reason, now, notifier)


@events_router.get("/{event_id}/review-flags", response_model=ReviewFlagsOut)
def list_review_flags(event_id: uuid.UUID, coordinator: Coordinator, db: Session = Depends(get_db)) -> ReviewFlagsOut:
    return ReviewFlagsOut(flags=review_flag_service.list_for_event(db, coordinator, event_id))


@flags_router.post("/{flag_id}/clear", response_model=ReviewFlagOut)
def clear_review_flag(
    flag_id: uuid.UUID,
    body: ClearFlagWrite,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> ReviewFlagOut:
    return review_flag_service.clear(db, coordinator, flag_id, body, now)
