import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.notification.service import Notifier, get_notifier
from app.registration.schemas import (
    OfferReleaseResponse,
    RegisterRequest,
    RegisterResponse,
    WaitlistJoinRequest,
    WaitlistJoinResponse,
    WithdrawResponse,
)
from app.registration.service import registration_service
from app.user.dependencies import get_current_attendee
from app.user.models import Attendee

router = APIRouter(prefix="/api/v1/registrations", tags=["registrations"])

# Nested under /events, per spec §3, since the resource in the URL is the event being
# registered for or waitlisted for — even though the state that changes is a Registration.
events_router = APIRouter(prefix="/api/v1/events", tags=["registrations"])


@events_router.post("/{event_id}/registrations", status_code=201)
def register(
    event_id: uuid.UUID,
    body: RegisterRequest,
    attendee: Attendee = Depends(get_current_attendee),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> RegisterResponse:
    return registration_service.register(db, event_id, attendee, body.answers, now)


@events_router.post("/{event_id}/waitlist", status_code=201)
def join_waitlist(
    event_id: uuid.UUID,
    body: WaitlistJoinRequest,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> WaitlistJoinResponse:
    return registration_service.join_waitlist(db, event_id, body.email, now)


@router.post("/{registration_id}/withdraw")
def withdraw(
    registration_id: uuid.UUID,
    attendee: Attendee = Depends(get_current_attendee),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> WithdrawResponse:
    return registration_service.withdraw(db, registration_id, attendee, now, notifier)


@router.post("/{registration_id}/expire-offer")
def expire_offer(
    registration_id: uuid.UUID,
    _: Attendee = Depends(get_current_attendee),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> OfferReleaseResponse:
    """Manual stand-in for the scheduled sweep (SCRUM-37). No scheduler this sprint."""
    return registration_service.expire_offer(db, registration_id, now, notifier)


@router.post("/{registration_id}/decline")
def decline_offer(
    registration_id: uuid.UUID,
    attendee: Attendee = Depends(get_current_attendee),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> OfferReleaseResponse:
    """Not in §3's endpoint list, but TC-US7-11 requires declining as a distinct action
    from letting the window lapse."""
    return registration_service.decline_offer(db, registration_id, attendee, now, notifier)
