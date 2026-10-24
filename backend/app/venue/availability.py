"""US13 (SCRUM-16): whether a venue can be occupied for a window, with its setup and turnaround.

One rule, used by the booking request (US22), by buffer edits (D31), by Venue Staff's evaluation
(AC 4, D36) and by US4's approval (Calvin): `evaluate_window` for a window not booked yet,
`evaluate_booking` for an existing booking. Both report every conflict with its overlap period and,
for a booking, its reference (AC 4), and whether the occupied window fits the opening hours (AC 5).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.venue.models import LIVE_BOOKING_STATUSES, Venue, VenueBlock, VenueBooking, occupied_window

VENUE_TIMEZONE = ZoneInfo("Asia/Singapore")


@dataclass(frozen=True)
class Window:
    starts_at: datetime
    ends_at: datetime

    def as_json(self) -> dict[str, str]:
        return {"starts_at": self.starts_at.isoformat(), "ends_at": self.ends_at.isoformat()}


@dataclass(frozen=True)
class Conflict:
    """Something already occupying part of the window (AC 3). `window` is the clashing booking's own
    times or the block's; `occupied` adds that booking's buffers (a block has none); `overlap` is
    the exact shared period (AC 4)."""

    kind: str  # "booking" or "block" (holds come with US25)
    window: Window
    occupied: Window
    overlap: Window
    reference: str | None = None  # a booking's VB- reference (D33); None for a block
    note: str | None = None  # a block's note
    booking_id: uuid.UUID | None = None


@dataclass(frozen=True)
class HoursBreach:
    """The occupied window runs outside the venue's opening hours on the booking's day (AC 5).
    `fields` says which end: starts_at (setup before opening), ends_at (turnaround after closing,
    or past midnight)."""

    opens_at: time
    closes_at: time
    fields: list[str]


@dataclass(frozen=True)
class Evaluation:
    occupied: Window
    conflicts: list[Conflict] = field(default_factory=list)
    outside_hours: HoursBreach | None = None

    @property
    def clear(self) -> bool:
        return not self.conflicts and self.outside_hours is None


def _overlap(a: Window, b: Window) -> Window:
    return Window(max(a.starts_at, b.starts_at), min(a.ends_at, b.ends_at))


def hours_breach(venue: Venue, booking_starts_at: datetime, occupied: Window) -> HoursBreach | None:
    """AC 5, compared as instants on the booking's Singapore day: setup may not start before opening
    and turnaround may not end after closing. Hours can't cross midnight (US20), so an occupied
    window that runs into the next day is always outside them."""
    day = booking_starts_at.astimezone(VENUE_TIMEZONE).date()
    opens = datetime.combine(day, venue.opens_at, VENUE_TIMEZONE)
    closes = datetime.combine(day, venue.closes_at, VENUE_TIMEZONE)
    fields = []
    if occupied.starts_at < opens:
        fields.append("starts_at")
    if occupied.ends_at > closes:
        fields.append("ends_at")
    return HoursBreach(venue.opens_at, venue.closes_at, fields) if fields else None


def _booking_conflicts(
    db: Session, venue_id: uuid.UUID, occupied: Window, exclude_booking_id: uuid.UUID | None
) -> list[Conflict]:
    """Live bookings (D21) whose stored occupied window overlaps this one, the exclusion
    constraint's rule. && on the range its GiST index holds."""
    window = func.tstzrange(literal(occupied.starts_at), literal(occupied.ends_at), literal("[)"))
    query = select(VenueBooking).where(
        VenueBooking.venue_id == venue_id,
        VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
        func.tstzrange(VenueBooking.occupied_starts_at, VenueBooking.occupied_ends_at, literal("[)")).op("&&")(window),
    )
    if exclude_booking_id is not None:
        query = query.where(VenueBooking.id != exclude_booking_id)
    conflicts = []
    for booking in db.scalars(query.order_by(VenueBooking.occupied_starts_at, VenueBooking.id)):
        theirs = Window(booking.occupied_starts_at, booking.occupied_ends_at)
        conflicts.append(
            Conflict(
                kind="booking",
                window=Window(booking.starts_at, booking.ends_at),
                occupied=theirs,
                overlap=_overlap(occupied, theirs),
                reference=booking.reference,
                booking_id=booking.id,
            )
        )
    return conflicts


def _block_conflicts(db: Session, venue_id: uuid.UUID, occupied: Window) -> list[Conflict]:
    """Venue blocks (US2's unavailability periods) overlapping the occupied window. A block has no
    buffers of its own (confirmed by the story owner), so its plain window is what's checked."""
    window = func.tstzrange(literal(occupied.starts_at), literal(occupied.ends_at), literal("[)"))
    blocks = db.scalars(
        select(VenueBlock)
        .where(
            VenueBlock.venue_id == venue_id,
            func.tstzrange(VenueBlock.starts_at, VenueBlock.ends_at, literal("[)")).op("&&")(window),
        )
        .order_by(VenueBlock.starts_at, VenueBlock.id)
    )
    conflicts = []
    for block in blocks:
        theirs = Window(block.starts_at, block.ends_at)
        conflicts.append(
            Conflict(kind="block", window=theirs, occupied=theirs, overlap=_overlap(occupied, theirs), note=block.note)
        )
    return conflicts


def _hold_conflicts(db: Session, venue_id: uuid.UUID, occupied: Window) -> list[Conflict]:
    # TODO(US25): unexpired tentative holds (AC 3) don't exist yet; SCRUM-93 adds them here.
    return []


def evaluate_window(
    db: Session,
    venue: Venue,
    starts_at: datetime,
    ends_at: datetime,
    *,
    exclude_booking_id: uuid.UUID | None = None,
) -> Evaluation:
    """What stands in the way of occupying `venue` for [starts_at, ends_at) plus its buffers (AC 1-5),
    with the venue as it is now. Conflicts are bookings first, then blocks, each by start."""
    occupied = Window(*occupied_window(venue, starts_at, ends_at))
    conflicts = (
        _booking_conflicts(db, venue.id, occupied, exclude_booking_id)
        + _block_conflicts(db, venue.id, occupied)
        + _hold_conflicts(db, venue.id, occupied)
    )
    return Evaluation(occupied=occupied, conflicts=conflicts, outside_hours=hours_breach(venue, starts_at, occupied))


def evaluate_booking(db: Session, booking: VenueBooking) -> Evaluation:
    """US4's check before approving (AC 3, 5): the booking as it would occupy its venue now, with the
    venue's current buffers and hours, against everything else. It ignores itself."""
    venue = db.get(Venue, booking.venue_id)
    return evaluate_window(db, venue, booking.starts_at, booking.ends_at, exclude_booking_id=booking.id)
