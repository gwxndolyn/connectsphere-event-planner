import enum
import uuid
from datetime import datetime, time, timedelta

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, Time, func, text
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
    APPROVED = "approved"  # Venue Staff approved it: the venue is reserved for the event (US4 AC 2)
    REJECTED = "rejected"  # Venue Staff rejected it, optionally with a reason and an alternative (US4 AC 5)
    WITHDRAWN = "withdrawn"  # the coordinator withdrew it while pending (AC 5)


class PreparationStatus(enum.StrEnum):
    """US24 AC 7 (D73, CS3-49): how far Venue staff are with getting a booked venue ready. Stored as
    text under venue_bookings_preparation_status_known."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    READY = "ready"


# D21 (decided by the team): Requested and Approved both block the window, from the sessions 1-2
# clarification behind AC 7, "any overlap is prevented; first come, first served". AC 3 lists only
# approved bookings, but first come, first served needs a pending request to hold the window too.
# The migration's exclusion constraint uses the same pair; change both together.
LIVE_BOOKING_STATUSES = (VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED)


def occupied_window(venue: "Venue", starts_at: datetime, ends_at: datetime) -> tuple[datetime, datetime]:
    """US13 AC 2: the venue is occupied from the start of setup to the end of turnaround, with the
    venue's own buffers (AC 1). 10:00-12:00 with 30/45 occupies 09:30-12:45; 0/0 is the plain window.
    The one place this is worked out: create, the seed, tests and (PR 2) buffer edits all call it."""
    return (
        starts_at - timedelta(minutes=venue.setup_minutes),
        ends_at + timedelta(minutes=venue.turnaround_minutes),
    )


class VenueBooking(Base):
    """A coordinator's request to hold a venue for an event (US22, SCRUM-89).

    The exclusion constraint `venue_bookings_no_overlap` refuses a Requested or Approved booking
    whose occupied window [occupied_starts_at, occupied_ends_at) overlaps another's at the same
    venue, even by one second; windows that only touch are allowed (US13 AC 3). It also settles
    AC 7's race, since a concurrent second insert waits for the first to commit and then fails. The
    migrations hold it and the CHECKs; the class mirrors the CHECKs. No buffer columns: setup and
    turnaround belong to the venue (US20 AC 7); a booking stores only the window they produce."""

    # DECISION-PENDING: D22 — since US13 PR 1 (SCRUM-114) the guard covers the occupied window, from
    # the venue's buffers when the booking is made. PR 2 recomputes it when buffers change (D31).
    # Holds (US25) don't exist yet.

    __tablename__ = "venue_bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="venue_bookings_window_valid"),
        CheckConstraint(
            "occupied_starts_at <= starts_at AND occupied_ends_at >= ends_at",
            name="venue_bookings_occupied_covers_window",
        ),
        CheckConstraint("expected_attendees >= 1", name="venue_bookings_expected_attendees_positive"),
        CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)", name="venue_bookings_withdrawn_consistent"
        ),
        # US4 (SCRUM-8): a decision time exactly when approved or rejected; notes only on a rejection.
        CheckConstraint(
            "(status IN ('approved', 'rejected')) = (decided_at IS NOT NULL)", name="venue_bookings_decided_consistent"
        ),
        CheckConstraint(
            "status = 'rejected' OR (rejection_reason IS NULL AND alternative_suggestion IS NULL)",
            name="venue_bookings_rejection_notes_only_when_rejected",
        ),
        # DECISION-PENDING: D51 — no one decides a booking they requested (US16b, SCRUM-120).
        CheckConstraint("decided_by_user_id <> requested_by_user_id", name="venue_bookings_decider_not_requester"),
        # DECISION-PENDING: D66 — US24 (SCRUM-127): a purpose of 1 to 100 characters, already trimmed.
        CheckConstraint(
            "purpose = btrim(purpose) AND char_length(purpose) BETWEEN 1 AND 100", name="venue_bookings_purpose_valid"
        ),
        # DECISION-PENDING: D68 — US24 AC 4: at most one live primary venue per event. A withdrawn or
        # rejected primary no longer counts. The same pair as LIVE_BOOKING_STATUSES; change both together.
        Index(
            "venue_bookings_one_primary_per_event",
            "event_id",
            unique=True,
            postgresql_where=text("is_primary AND status IN ('requested', 'approved')"),
        ),
        # DECISION-PENDING: D73 — preparation is tracked per venue (CS3-49); PreparationStatus's values.
        CheckConstraint(
            "preparation_status IN ('not_started', 'in_progress', 'ready')",
            name="venue_bookings_preparation_status_known",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id"))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # US13: [starts_at - setup, ends_at + turnaround), from occupied_window(). The overlap guard's range.
    occupied_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occupied_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # DECISION-PENDING: D33 — VB-<year>-<6+ digits>, from next_venue_booking_reference() (the
    # migration), so every insert gets one. US13 AC 4 names a conflicting booking by it.
    reference: Mapped[str] = mapped_column(
        Text, unique=True, server_default=text("next_venue_booking_reference()")
    )
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
    # US4 (SCRUM-8): Venue Staff's decision. decided_by_user_id is null only for a decision older
    # than US4 (the migration backfills decided_at for those). The two notes go with a rejection (AC 5).
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    alternative_suggestion: Mapped[str | None] = mapped_column(Text)
    # US24 (SCRUM-92, PR 1 SCRUM-127) AC 1: what this venue is for, e.g. "Main hall" or "Breakout A".
    # The default is the migration's backfill, and keeps US22's create working until PR 2 asks for one.
    purpose: Mapped[str] = mapped_column(Text, server_default=text("'Main venue'"))
    # AC 4: the one venue attendees see (D68, D70).
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # AC 7: Venue staff move an approved booking on from not_started (PR 2's endpoint, PR 3's screen).
    preparation_status: Mapped[str] = mapped_column(Text, server_default=text("'not_started'"))


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
