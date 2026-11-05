from datetime import datetime
from zoneinfo import ZoneInfo

from app.event.models import DeliveryMode, Event

# Preferred dates and times are Singapore days and clock times (D9).
EVENT_TIMEZONE = ZoneInfo("Asia/Singapore")


def preferred_window(event: Event) -> tuple[datetime | None, datetime | None]:
    """DECISION-PENDING: D123 — the event's date at approval: its earliest preferred date, at its preferred
    start and end times, Singapore time (the customer's CS1: one date per request). None where a
    preference is missing; a submitted request always holds them (REQUIRED_FIELDS)."""
    if not event.preferred_dates:
        return None, None
    day = min(event.preferred_dates)
    starts_at = datetime.combine(day, event.preferred_start_time, tzinfo=EVENT_TIMEZONE) if event.preferred_start_time else None
    ends_at = datetime.combine(day, event.preferred_end_time, tzinfo=EVENT_TIMEZONE) if event.preferred_end_time else None
    return starts_at, ends_at


def fill_final_fields(event: Event, *, starts_at: datetime | None, ends_at: datetime | None, capacity: int | None) -> None:
    """A request has no date, capacity or delivery mode of its own, and Planning onwards needs them
    (events_final_fields_required). Approving (US17, D53) and confirming (US18, D86) fill them; anything
    the event already holds is kept. The request form doesn't ask for a delivery mode, so it's in person."""
    event.start_at = event.start_at or starts_at
    event.end_at = event.end_at or ends_at
    if event.capacity is None:
        event.capacity = capacity
    event.delivery_mode = event.delivery_mode or DeliveryMode.IN_PERSON
