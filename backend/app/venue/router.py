import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.user.dependencies import get_current_user, require_user_roles
from app.user.models import User
from app.venue.schemas import VenueOut, VenuesOut, VenueWrite
from app.venue.service import VENUE_STAFF_ROLES, venue_service

router = APIRouter(prefix="/api/v1/venues", tags=["venues"])

VenueStaff = Annotated[User, Depends(require_user_roles(*VENUE_STAFF_ROLES))]


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
