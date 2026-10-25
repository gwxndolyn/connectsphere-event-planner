import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.registration.models import RegistrationStatus
from app.registration.roster_service import registration_roster_service
from app.registration.schemas import EventRegistrationsResponse, ManagedEventsResponse
from app.user.dependencies import require_user_roles
from app.user.models import User, UserRole

# US28 (SCRUM-96). Staff routes, so X-User-Id or a token, not the attendee stub. Same /events prefix
# as registering (POST), since the resource is still the event's registrations.
events_router = APIRouter(prefix="/api/v1/events", tags=["event-registrations"])
me_router = APIRouter(prefix="/api/v1/me", tags=["event-registrations"])

# US28's two roles: the Organiser who created the event and its assigned Coordinator (D52).
Manager = Annotated[User, Depends(require_user_roles(UserRole.ORGANISER, UserRole.COORDINATOR))]


@me_router.get("/managed-events")
def list_managed_events(manager: Manager, db: Session = Depends(get_db)) -> ManagedEventsResponse:
    return ManagedEventsResponse(events=registration_roster_service.list_managed_events(db, manager))


@events_router.get("/{event_id}/registrations")
def list_event_registrations(
    event_id: uuid.UUID,
    manager: Manager,
    status: Annotated[list[RegistrationStatus] | None, Query()] = None,
    show_all: bool = False,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> EventRegistrationsResponse:
    return registration_roster_service.list_registrations(db, event_id, manager, now, status, show_all)
