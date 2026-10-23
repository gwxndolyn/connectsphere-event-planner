import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.notification.service import Notifier, get_notifier
from app.user.dependencies import require_user_roles
from app.user.models import User, UserRole
from app.venue.booking_service import booking_service
from app.venue.schemas import VenueBookingCreatedOut, VenueBookingOut, VenueBookingsOut, VenueBookingWrite
from app.venue.service import VENUE_STAFF_ROLES

router = APIRouter(prefix="/api/v1/venue-bookings", tags=["venue-bookings"])
# An event's bookings hang off the event, like its registrations do.
events_router = APIRouter(prefix="/api/v1/events", tags=["venue-bookings"])

Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]
VenueStaff = Annotated[User, Depends(require_user_roles(*VENUE_STAFF_ROLES))]
BookingReader = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR, *VENUE_STAFF_ROLES))]


@router.post("", status_code=201, response_model=VenueBookingCreatedOut)
def request_venue(
    body: VenueBookingWrite,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> VenueBookingCreatedOut:
    return booking_service.create(db, coordinator, body, now, notifier)


@router.get("/pending", response_model=VenueBookingsOut)
def pending_bookings(_: VenueStaff, db: Session = Depends(get_db)) -> VenueBookingsOut:
    return VenueBookingsOut(bookings=booking_service.pending(db))


@router.post("/{booking_id}/withdraw", response_model=VenueBookingOut)
def withdraw_booking(
    booking_id: uuid.UUID,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> VenueBookingOut:
    return booking_service.withdraw(db, coordinator, booking_id, now)


@events_router.get("/{event_id}/venue-bookings", response_model=VenueBookingsOut)
def event_bookings(event_id: uuid.UUID, reader: BookingReader, db: Session = Depends(get_db)) -> VenueBookingsOut:
    return VenueBookingsOut(bookings=booking_service.for_event(db, reader, event_id))
