import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.event.edit_schemas import CoordinatedEventsOut, EventDetailsOut, EventEditOut, EventEditWrite, EventHistoryOut
from app.event.edit_service import event_edit_service
from app.user.dependencies import require_user_roles
from app.user.models import User, UserRole

# US12 (SCRUM-15): an event past the request stage, for its assigned coordinator. The request routes stop
# at `rejected` (D11), so these are the event's own.
router = APIRouter(prefix="/api/v1/events", tags=["event-edits"])
me_router = APIRouter(prefix="/api/v1/me", tags=["event-edits"])

Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]


@me_router.get("/coordinated-events", response_model=CoordinatedEventsOut)
def my_coordinated_events(coordinator: Coordinator, db: Session = Depends(get_db)) -> CoordinatedEventsOut:
    return CoordinatedEventsOut(events=event_edit_service.list_mine(db, coordinator))


@router.get("/{event_id}", response_model=EventDetailsOut)
def event_details(event_id: uuid.UUID, coordinator: Coordinator, db: Session = Depends(get_db)) -> EventDetailsOut:
    return event_edit_service.details(db, coordinator, event_id)


@router.patch("/{event_id}", response_model=EventEditOut)
def edit_event(
    event_id: uuid.UUID,
    body: EventEditWrite,
    coordinator: Coordinator,
    response: Response,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> EventEditOut:
    result, status_code = event_edit_service.edit(db, coordinator, event_id, body, now)
    response.status_code = status_code
    return result


@router.get("/{event_id}/history", response_model=EventHistoryOut)
def event_history(event_id: uuid.UUID, coordinator: Coordinator, db: Session = Depends(get_db)) -> EventHistoryOut:
    return EventHistoryOut(entries=event_edit_service.history(db, coordinator, event_id))
