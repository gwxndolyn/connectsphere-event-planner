import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.notification.service import Notifier, get_notifier
from app.user.dependencies import require_user_roles
from app.user.models import User, UserRole
from app.venue.booking_service import booking_service
from app.venue.schemas import (
    BookingApproveWrite,
    BookingEvaluationOut,
    BookingPreparationWrite,
    BookingRejectWrite,
    EventVenueBookingsOut,
    HoldEventsOut,
    VenueBookingCreatedOut,
    VenueBookingOut,
    VenueBookingsOut,
    VenueBookingWrite,
    VenueHoldWrite,
)
from app.venue.service import VENUE_STAFF_ROLES

router = APIRouter(prefix="/api/v1/venue-bookings", tags=["venue-bookings"])
# An event's bookings hang off the event, like its registrations do.
events_router = APIRouter(prefix="/api/v1/events", tags=["venue-bookings"])
# US25 (SCRUM-93): Venue staff's holds, and the events they may hold a venue for.
holds_router = APIRouter(prefix="/api/v1/venue-holds", tags=["venue-bookings"])

Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]
VenueStaff = Annotated[User, Depends(require_user_roles(*VENUE_STAFF_ROLES))]
# US24 (SCRUM-128, D71): the event's Organiser reads its venues too; the service checks it's theirs.
BookingReader = Annotated[
    User, Depends(require_user_roles(UserRole.ORGANISER, UserRole.COORDINATOR, *VENUE_STAFF_ROLES))
]


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
def pending_bookings(
    _: VenueStaff,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> VenueBookingsOut:
    return VenueBookingsOut(bookings=booking_service.pending(db, now, notifier))


@router.get("/{booking_id}/evaluation", response_model=BookingEvaluationOut)
def booking_evaluation(booking_id: uuid.UUID, _: VenueStaff, db: Session = Depends(get_db)) -> BookingEvaluationOut:
    # US13 AC 4 (D36): conflicts with their overlap and reference, and any hours breach.
    return booking_service.evaluation(db, booking_id)


@router.post("/{booking_id}/withdraw", response_model=VenueBookingOut)
def withdraw_booking(
    booking_id: uuid.UUID,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> VenueBookingOut:
    # US24 (D69): an approved booking too; Venue staff are told.
    return booking_service.withdraw(db, coordinator, booking_id, now, notifier)


@router.post("/{booking_id}/make-primary", response_model=VenueBookingOut)
def make_primary(
    booking_id: uuid.UUID,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> VenueBookingOut:
    # US24 AC 4 (D68): the venue attendees see.
    return booking_service.make_primary(db, coordinator, booking_id, now, notifier)


@router.post("/{booking_id}/preparation", response_model=VenueBookingOut)
def set_preparation(
    booking_id: uuid.UUID,
    staff: VenueStaff,
    body: BookingPreparationWrite | None = Body(default=None),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> VenueBookingOut:
    # US24 AC 7 (D73): how far Venue staff are with getting an approved venue ready.
    return booking_service.set_preparation(db, staff, booking_id, body or BookingPreparationWrite(), now)


@router.post("/{booking_id}/approve", response_model=VenueBookingOut)
def approve_booking(
    booking_id: uuid.UUID,
    staff: VenueStaff,
    # US4 AC 7: nothing to send. Any field (a different layout, say) is refused, so no partial approval.
    _: BookingApproveWrite | None = Body(default=None),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> VenueBookingOut:
    return booking_service.approve(db, staff, booking_id, now, notifier)


@router.post("/{booking_id}/reject", response_model=VenueBookingOut)
def reject_booking(
    booking_id: uuid.UUID,
    staff: VenueStaff,
    body: BookingRejectWrite | None = Body(default=None),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> VenueBookingOut:
    return booking_service.reject(db, staff, booking_id, body or BookingRejectWrite(), now, notifier)


@events_router.get("/{event_id}/venue-bookings", response_model=EventVenueBookingsOut)
def event_bookings(
    event_id: uuid.UUID,
    reader: BookingReader,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> EventVenueBookingsOut:
    return booking_service.for_event(db, reader, event_id, now, notifier)


# US25 (SCRUM-93) AC 5: the event's coordinator confirms a held venue into a request for Venue staff to approve.
# Declining one is withdraw (AC 7, D104).
@router.post("/{booking_id}/confirm", response_model=VenueBookingOut)
def confirm_hold(
    booking_id: uuid.UUID,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> VenueBookingOut:
    return booking_service.confirm_hold(db, coordinator, booking_id, now, notifier)


# US25 AC 1: Venue staff hold a venue for an event and time, until an expiry.
@holds_router.post("", status_code=201, response_model=VenueBookingCreatedOut)
def place_hold(
    body: VenueHoldWrite,
    staff: VenueStaff,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> VenueBookingCreatedOut:
    return booking_service.place_hold(db, staff, body, now, notifier)


@holds_router.get("/events", response_model=HoldEventsOut)
def hold_events(_: VenueStaff, db: Session = Depends(get_db)) -> HoldEventsOut:
    return HoldEventsOut(events=booking_service.hold_events(db))
