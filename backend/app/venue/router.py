import uuid
from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.user.dependencies import get_current_user, require_user_roles
from app.user.models import User
from app.venue.schemas import VenueOut, VenueSearchOut, VenuesOut, VenueWrite
from app.venue.service import VENUE_SEARCH_ROLES, VENUE_STAFF_ROLES, venue_service

router = APIRouter(prefix="/api/v1/venues", tags=["venues"])

VenueStaff = Annotated[User, Depends(require_user_roles(*VENUE_STAFF_ROLES))]
VenueSearcher = Annotated[User, Depends(require_user_roles(*VENUE_SEARCH_ROLES))]


@router.get("", response_model=VenuesOut)
def list_venues(
    reader: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str | None = None,
    min_capacity: int | None = None,
    facilities: Annotated[list[str] | None, Query()] = None,
    accessibility: Annotated[list[str] | None, Query()] = None,
    active: bool | None = None,
) -> VenuesOut:
    return VenuesOut(
        venues=venue_service.search(
            db,
            reader,
            q=q,
            min_capacity=min_capacity,
            facilities=facilities,
            accessibility=accessibility,
            active=active,
        )
    )


# Declared before /{venue_id}, which would otherwise take "available" as an id.
@router.get("/available", response_model=VenueSearchOut)
def search_available_venues(
    _: VenueSearcher,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    # Optional here so a missing one is MISSING_REQUIRED_FIELD naming every gap, not FastAPI's 422.
    date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    # A string, so 1.5 or "lots" reaches the service and is INVALID_VENUE_SEARCH on `attendees`
    # instead of FastAPI's generic 422, which names no field the form can mark.
    attendees: str | None = None,
    location: str | None = None,
    facilities: Annotated[list[str] | None, Query()] = None,
    accessibility: Annotated[list[str] | None, Query()] = None,
) -> VenueSearchOut:
    return venue_service.find_available(
        db,
        now,
        on=date,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        location=location,
        facilities=facilities,
        accessibility=accessibility,
    )


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(
    venue_id: uuid.UUID,
    reader: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VenueOut:
    return venue_service.get(db, venue_id, reader)


@router.post("", status_code=201, response_model=VenueOut)
def create_venue(body: VenueWrite, _: VenueStaff, db: Session = Depends(get_db)) -> VenueOut:
    return venue_service.create(db, body)


@router.patch("/{venue_id}", response_model=VenueOut)
def update_venue(
    venue_id: uuid.UUID,
    body: VenueWrite,
    _: VenueStaff,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> VenueOut:
    return venue_service.update(db, venue_id, body, now)


@router.post("/{venue_id}/deactivate", response_model=VenueOut)
def deactivate_venue(venue_id: uuid.UUID, _: VenueStaff, db: Session = Depends(get_db)) -> VenueOut:
    return venue_service.set_active(db, venue_id, False)


@router.post("/{venue_id}/reactivate", response_model=VenueOut)
def reactivate_venue(venue_id: uuid.UUID, _: VenueStaff, db: Session = Depends(get_db)) -> VenueOut:
    return venue_service.set_active(db, venue_id, True)
