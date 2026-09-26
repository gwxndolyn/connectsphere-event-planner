from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.event.schemas import AvailableEventsResponse
from app.event.service import event_service
from app.user.dependencies import get_current_attendee
from app.user.models import Attendee

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/health")
def health() -> str:
    return event_service.health()


# Everything below is spec §3, prefixed /api/v1 per its "Prefix everything /api/v1" rule.
# `/api/events/health` above predates that spec and is left alone — it's load-bearing for the
# e2e wait-on check and unrelated to SCRUM-2/5/6.
v1_router = APIRouter(prefix="/api/v1/events", tags=["events"])


@v1_router.get("/available")
def list_available(
    attendee: Attendee = Depends(get_current_attendee),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> AvailableEventsResponse:
    return event_service.list_available(db, attendee, now)
