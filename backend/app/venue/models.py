import enum
import uuid
from datetime import datetime, time

from sqlalchemy import ARRAY, CheckConstraint, DateTime, ForeignKey, Integer, Text, Time, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, pg_enum

# DECISION-PENDING: D18 — SCRUM-87 only gives examples (projector, stage, wifi; wheelchair, lift;
# theatre, classroom, banquet). These are the assumed vocabularies, so US2's filters and the
# venue form agree on spelling.
# Two migrations hold copies of these lists in their CHECKs: migrations/versions/20261013_1200_us20_venues.py
# (venues' tags) and migrations/versions/20261021_1200_us22_bookings.py (bookings' layout and tags).
# Change all three together, by a new migration that replaces both sets of CHECKs; the frontend's
# frontend/src/features/venue/tags.ts mirrors them too.
FACILITIES = (
    "projector",
    "screen",
    "sound_system",
    "microphone",
    "stage",
    "wifi",
    "whiteboard",
    "video_conferencing",
    "power_outlets",
)
ACCESSIBILITY_FEATURES = (
    "wheelchair",
    "lift",
    "accessible_toilet",
    "hearing_loop",
    "step_free_entrance",
)
ROOM_LAYOUTS = (
    "theatre",
    "classroom",
    "banquet",
    "boardroom",
    "u_shape",
    "cabaret",
    "standing",
)


class Venue(Base):
    """A bookable venue in the catalogue (US20, SCRUM-87). One venue hosts one event at a time;
    there are no separately bookable rooms inside it. Setup and turnaround buffers belong to the
    venue only: a booking can't override them for a single event (AC 7). The table's CHECK
    constraints are the source of truth; the class mirrors them for readers."""

    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="venues_name_not_blank"),
        CheckConstraint("btrim(location) <> ''", name="venues_location_not_blank"),
        CheckConstraint("capacity > 0", name="venues_capacity_positive"),
        CheckConstraint("closes_at > opens_at", name="venues_hours_valid"),
        CheckConstraint("setup_minutes >= 0", name="venues_setup_minutes_non_negative"),
        CheckConstraint("turnaround_minutes >= 0", name="venues_turnaround_minutes_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text)
    capacity: Mapped[int] = mapped_column(Integer)
    facilities: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    accessibility_features: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    room_layouts: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    opens_at: Mapped[time] = mapped_column(Time)
    closes_at: Mapped[time] = mapped_column(Time)
    setup_minutes: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    turnaround_minutes: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class VenueBookingStatus(enum.StrEnum):
    REQUESTED = "requested"  # pending Venue Staff's review (US22 AC 4)
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"  # the coordinator withdrew it while pending (AC 5)


# D21 (decided by the team): Requested and Approved both block the window, from the sessions 1-2
# clarification behind AC 7, "any overlap is prevented; first come, first served". AC 3 lists only
# approved bookings, but first come, first served needs a pending request to hold the window too.
# The migration's exclusion constraint uses the same pair; change both together.
LIVE_BOOKING_STATUSES = (VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED)


class VenueBooking(Base):
    """A coordinator's request to hold a venue for an event (US22, SCRUM-89).

    The exclusion constraint `venue_bookings_no_overlap` refuses a Requested or Approved booking
    whose [starts_at, ends_at) overlaps another at the same venue, even by one second; back-to-back
    is allowed. It also settles AC 7's race, since a concurrent second insert waits for the first
    to commit and then fails. The migration holds it and the CHECKs; the class mirrors the CHECKs.
    No buffer columns: setup and turnaround belong to the venue (US20 AC 7)."""

    # DECISION-PENDING: D22 — the window is plain start to end. US13 (SCRUM-16) adds the venue's
    # setup and turnaround to it; holds (US25) and unavailability (US23a) don't exist yet.

    __tablename__ = "venue_bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="venue_bookings_window_valid"),
        CheckConstraint("expected_attendees >= 1", name="venue_bookings_expected_attendees_positive"),
        CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)", name="venue_bookings_withdrawn_consistent"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id"))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expected_attendees: Mapped[int] = mapped_column(Integer)
    room_layout: Mapped[str] = mapped_column(Text)  # one of ROOM_LAYOUTS
    # DECISION-PENDING: D23 — the event's equipment_needs and accessibility_needs are free text and
    # can't be matched against a venue, so the request carries D18 tags (FACILITIES and
    # ACCESSIBILITY_FEATURES) that PR 2 compares with the venue's to warn about gaps.
    required_facilities: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    required_accessibility_features: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    special_requirements: Mapped[str | None] = mapped_column(Text)
    status: Mapped[VenueBookingStatus] = mapped_column(
        pg_enum(VenueBookingStatus, "venue_booking_status"), server_default=VenueBookingStatus.REQUESTED.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Any ORM update stamps the time unless the caller sets it (withdraw passes its clock).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VenueBlock(Base):
    """A time a venue is out of use with no event behind it, e.g. maintenance or a closure (US2 AC 5,
    SCRUM-7). Search leaves a venue out while a block overlaps the requested time, as it does for a
    live booking. US23a (SCRUM-90, CR-02) adds Venue Staff's screens for these. Blocks may overlap
    each other; only bookings are kept apart."""

    __tablename__ = "venue_blocks"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="venue_blocks_window_valid"),
        # Also venue_blocks_venue_window: GiST on (venue_id, tstzrange(starts_at, ends_at, '[)')),
        # defined in the migration, the expression search's && overlap uses.
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
