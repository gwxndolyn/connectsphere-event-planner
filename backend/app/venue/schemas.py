import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict

from app.event.models import EventStatus
from app.venue.models import VenueBookingStatus


class VenueWrite(BaseModel):
    """Create and edit body. Every field is optional here so the service can list every missing
    field at once (`MISSING_REQUIRED_FIELD`) instead of FastAPI's generic 422; on edit, only the
    fields sent change."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    location: str | None = None
    capacity: int | None = None
    facilities: list[str] | None = None
    accessibility_features: list[str] | None = None
    room_layouts: list[str] | None = None
    opens_at: time | None = None
    closes_at: time | None = None
    setup_minutes: int | None = None
    turnaround_minutes: int | None = None


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    location: str
    capacity: int
    facilities: list[str]
    accessibility_features: list[str]
    room_layouts: list[str]
    opens_at: time
    closes_at: time
    setup_minutes: int
    turnaround_minutes: int
    is_active: bool


class VenuesOut(BaseModel):
    venues: list[VenueOut]


class VenueBookingWrite(BaseModel):
    """Booking request body (US22). Optional here so the service lists every missing field at once.
    Unknown fields are rejected, so a booking can't send its own setup or turnaround (US20 AC 7)."""

    model_config = ConfigDict(extra="forbid")

    event_id: uuid.UUID | None = None
    venue_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    expected_attendees: int | None = None
    room_layout: str | None = None
    required_facilities: list[str] | None = None
    required_accessibility_features: list[str] | None = None
    special_requirements: str | None = None


class BookingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    request_reference: str | None
    status: EventStatus


class BookingVenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    location: str
    capacity: int


class VenueBookingOut(BaseModel):
    id: uuid.UUID
    event: BookingEventOut
    venue: BookingVenueOut
    requested_by_user_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    expected_attendees: int
    room_layout: str
    required_facilities: list[str]
    required_accessibility_features: list[str]
    special_requirements: str | None
    status: VenueBookingStatus
    created_at: datetime
    updated_at: datetime
    withdrawn_at: datetime | None
    # US4 (SCRUM-8): Venue Staff's decision, null while pending or once withdrawn.
    decided_at: datetime | None
    decided_by_user_id: uuid.UUID | None
    rejection_reason: str | None
    alternative_suggestion: str | None


class BookingApproveWrite(BaseModel):
    """Approve body (US4). A request is approved as a whole (AC 7), so there is nothing to send:
    any field, such as a different layout or time, is an unknown field and refused."""

    model_config = ConfigDict(extra="forbid")


class BookingRejectWrite(BaseModel):
    """Reject body (US4 AC 5): both optional; blank is the same as leaving it out."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = None
    alternative_suggestion: str | None = None


class BookingWarning(BaseModel):
    """Something the request needs that the venue lacks (AC 3): the request still saves."""

    field: str
    item: str
    message: str


class VenueBookingCreatedOut(VenueBookingOut):
    warnings: list[BookingWarning]


class VenueBookingsOut(BaseModel):
    bookings: list[VenueBookingOut]


class VenueSearchCriteria(BaseModel):
    """The search as the service understood it, echoed so the screen can say what was applied
    (US2 AC 7). Tags are in D18's order and the location trimmed."""

    date: date
    start_time: time
    end_time: time
    attendees: int
    location: str | None
    facilities: list[str]
    accessibility: list[str]


class VenueSearchOut(BaseModel):
    venues: list[VenueOut]
    criteria: VenueSearchCriteria
