import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

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
    reference: str  # US13 D33
    starts_at: datetime
    ends_at: datetime
    # US13: [starts_at - setup, ends_at + turnaround), as the overlap guard holds it.
    occupied_starts_at: datetime
    occupied_ends_at: datetime
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


NOTE_MAX_LENGTH = 1000


class BookingRejectWrite(BaseModel):
    """Reject body (US4 AC 5): both optional; blank is the same as leaving it out."""

    model_config = ConfigDict(extra="forbid")

    # Stored, logged and shown to the coordinator, so kept to a readable length (PR #73 review).
    reason: str | None = Field(default=None, max_length=NOTE_MAX_LENGTH)
    alternative_suggestion: str | None = Field(default=None, max_length=NOTE_MAX_LENGTH)


class BookingWarning(BaseModel):
    """Something the request needs that the venue lacks (AC 3): the request still saves."""

    field: str
    item: str
    message: str


class VenueBookingCreatedOut(VenueBookingOut):
    warnings: list[BookingWarning]


class VenueBookingsOut(BaseModel):
    bookings: list[VenueBookingOut]


class WindowOut(BaseModel):
    starts_at: datetime
    ends_at: datetime


class BookingConflictOut(BaseModel):
    """US13 AC 4: something occupying part of the booking's window. starts_at/ends_at are the
    clashing booking's own times or the block's; `occupied` adds that booking's buffers."""

    kind: str  # "booking" or "block"
    reference: str | None
    note: str | None
    starts_at: datetime
    ends_at: datetime
    occupied: WindowOut
    overlap: WindowOut


class BookingHoursOut(BaseModel):
    """US13 AC 5: the occupied window runs outside these hours; `fields` names the end."""

    opens_at: time
    closes_at: time
    fields: list[str]


class BookingEvaluationOut(BaseModel):
    """GET /api/v1/venue-bookings/{id}/evaluation (D36): what stands in the way of the booking now."""

    booking_id: uuid.UUID
    reference: str
    occupied: WindowOut
    conflicts: list[BookingConflictOut]
    outside_hours: BookingHoursOut | None
    clear: bool


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


class CalendarVenueOut(BaseModel):
    """US21: the venue the calendar is for, with what the screen needs to draw it: its hours (shaded
    outside them, D61) and its buffers (AC 2)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    opens_at: time
    closes_at: time
    setup_minutes: int
    turnaround_minutes: int


class CalendarEventOut(BaseModel):
    """US21 AC 3: the booked event's name (or, unnamed, its reference) and status. No id: the
    calendar doesn't lead into the request, which D48 keeps to its own coordinator (D58)."""

    name: str | None
    request_reference: str | None
    status: EventStatus


class CalendarBookingOut(BaseModel):
    id: uuid.UUID
    # DECISION-PENDING: D58 — null unless the reader is Venue Staff, a Lead or the event's
    # coordinator, as a coordinator's VENUE_UNAVAILABLE never names another booking (D35).
    reference: str | None
    status: VenueBookingStatus  # requested or approved (D57)
    event: CalendarEventOut


class CalendarItemOut(BaseModel):
    """One thing occupying the venue (US21 AC 1). starts_at/ends_at are the booking's own times or
    the block's; `occupied` adds the booking's setup and turnaround (AC 2) and equals them for a block."""

    kind: str  # "booking" or "block"; "hold" with US25 (D59)
    label: str  # "Booking", "Unavailable"; "Hold" with US25
    starts_at: datetime
    ends_at: datetime
    occupied: WindowOut
    booking: CalendarBookingOut | None
    note: str | None  # a block's note


class VenueCalendarOut(BaseModel):
    """GET /api/v1/venues/{id}/calendar (US21): what occupies the venue over `from`..`to`,
    Singapore days, both included (D61)."""

    model_config = ConfigDict(populate_by_name=True)

    venue: CalendarVenueOut
    from_: date = Field(alias="from")
    to: date
    items: list[CalendarItemOut]
