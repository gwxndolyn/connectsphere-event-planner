"""US21 (SCRUM-88, PR 1 SCRUM-122): a venue's availability calendar.

What occupies a venue over a range of Singapore days: its live bookings with their stored occupied
windows (US13, kept current by D31) and its blocks (US2). An item is in range if its occupied window
overlaps it, so a booking whose setup starts the evening before still shows (D61). Opening hours
come back with the venue for the screen to shade; they aren't items.
"""

import re
import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event
from app.user.models import User, UserRole
from app.venue.availability import VENUE_TIMEZONE, Window, block_conflicts
from app.venue.models import LIVE_BOOKING_STATUSES, VenueBooking
from app.venue.schemas import (
    CalendarBookingOut,
    CalendarEventOut,
    CalendarItemOut,
    CalendarVenueOut,
    VenueCalendarOut,
    WindowOut,
)
from app.venue.service import VENUE_STAFF_ROLES, venue_service

# DECISION-PENDING: D61 — a month view's six weeks; anything longer is INVALID_DATE_RANGE.
MAX_RANGE_DAYS = 42

# DECISION-PENDING: D58 — who sees every booking's VB- reference; a coordinator sees it only on
# their own events' bookings, as a coordinator's VENUE_UNAVAILABLE never names another's (D35).
REFERENCE_ROLES = (*VENUE_STAFF_ROLES, UserRole.COORDINATOR_LEAD)

# Only YYYY-MM-DD: date.fromisoformat also takes 20261012 and 2026-W42-1. ASCII digits only.
DAY_FORMAT = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)


def _parse_range(start: str | None, end: str | None) -> tuple[date, date]:
    """`from` and `to` as YYYY-MM-DD, `to` not before `from`, at most MAX_RANGE_DAYS days. Strings, so
    a missing or bad one names its field instead of FastAPI's generic 422 (deviation 51)."""
    days: dict[str, date] = {}
    bad: list[str] = []
    for field, value in (("from", start), ("to", end)):
        try:
            if not DAY_FORMAT.fullmatch(value or ""):
                raise ValueError(value)
            # Also refuses a well-formed day that doesn't exist, e.g. 2026-02-30.
            days[field] = date.fromisoformat(value)
        except ValueError:
            bad.append(field)
    if not bad and not 0 <= (days["to"] - days["from"]).days < MAX_RANGE_DAYS:
        bad.append("to")
    if bad:
        raise DomainError(
            422,
            "INVALID_DATE_RANGE",
            fields=bad,
            message=f"Choose a from and to date (YYYY-MM-DD), to not before from, at most {MAX_RANGE_DAYS} days.",
        )
    return days["from"], days["to"]


def _window_out(window: Window) -> WindowOut:
    return WindowOut(starts_at=window.starts_at, ends_at=window.ends_at)


def _booking_items(db: Session, venue_id: uuid.UUID, window: Window, reader: User) -> list[tuple[Window, CalendarItemOut]]:
    """Live bookings (D21, D57: Requested too) whose stored occupied window overlaps the range, on
    the range the exclusion constraint's GiST index holds. Withdrawn and rejected aren't live. A live
    booking for a cancelled event is shown, with the event's status, because it still holds the window."""
    # D60 decided (the PO, 30 Oct): a cancelled event's live bookings are shown. Whether cancelling an
    # event withdraws them is US9's (SCRUM-12).
    rows = db.execute(
        select(VenueBooking, Event)
        .join(Event, Event.id == VenueBooking.event_id)
        .where(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
            func.tstzrange(VenueBooking.occupied_starts_at, VenueBooking.occupied_ends_at, literal("[)")).op("&&")(
                func.tstzrange(literal(window.starts_at), literal(window.ends_at), literal("[)"))
            ),
        )
        .order_by(VenueBooking.occupied_starts_at, VenueBooking.id)
    )
    sees_every_reference = reader.holds(*REFERENCE_ROLES)
    items = []
    for booking, event in rows:
        occupied = Window(booking.occupied_starts_at, booking.occupied_ends_at)
        reference = booking.reference if sees_every_reference or event.coordinator_id == reader.id else None
        items.append(
            (
                occupied,
                CalendarItemOut(
                    kind="booking",
                    label="Booking",
                    starts_at=booking.starts_at,
                    ends_at=booking.ends_at,
                    occupied=_window_out(occupied),
                    booking=CalendarBookingOut(
                        id=booking.id,
                        reference=reference,
                        status=booking.status,
                        event=CalendarEventOut(
                            name=event.name, request_reference=event.request_reference, status=event.status
                        ),
                        preparation_status=booking.preparation_status,
                    ),
                    note=None,
                ),
            )
        )
    return items


def _block_items(db: Session, venue_id: uuid.UUID, window: Window) -> list[tuple[Window, CalendarItemOut]]:
    """US2's blocks overlapping the range, by US13's own check; a block has no buffers (D22)."""
    return [
        (
            block.occupied,
            CalendarItemOut(
                kind="block",
                label="Unavailable",
                starts_at=block.window.starts_at,
                ends_at=block.window.ends_at,
                occupied=_window_out(block.occupied),
                booking=None,
                note=block.note,
            ),
        )
        for block in block_conflicts(db, venue_id, window)
    ]


def _hold_items(db: Session, venue_id: uuid.UUID, window: Window) -> list[tuple[Window, CalendarItemOut]]:
    # DECISION-PENDING: D59 — TODO(US25): tentative holds don't exist yet. SCRUM-93 adds them here,
    # kind "hold", label "Hold", leaving out expired ones (AC 4).
    return []


class CalendarService:
    def calendar(self, db: Session, venue_id: uuid.UUID, reader: User, start: str | None, end: str | None) -> VenueCalendarOut:
        first, last = _parse_range(start, end)
        venue = venue_service.visible(db, venue_id, reader)
        window = Window(
            datetime.combine(first, time.min, VENUE_TIMEZONE),
            datetime.combine(last + timedelta(days=1), time.min, VENUE_TIMEZONE),
        )
        items = (
            _booking_items(db, venue.id, window, reader)
            + _block_items(db, venue.id, window)
            + _hold_items(db, venue.id, window)
        )
        # By occupied start; at the same start, bookings before blocks (the list's own order, stable sort).
        items.sort(key=lambda item: item[0].starts_at)
        return VenueCalendarOut(
            venue=CalendarVenueOut.model_validate(venue), from_=first, to=last, items=[item for _, item in items]
        )


calendar_service = CalendarService()
