"""US24 (SCRUM-92, PR 2 SCRUM-128) AC 4: the one venue attendees see for an event, its primary venue.

Imports models only, so the attendee services (events board, registration, My events) can use it
without depending on the venue services.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import Event
from app.venue.models import Venue, VenueBooking, VenueBookingStatus


def primary_venues(db: Session, event_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Venue]:
    """Each event's approved primary venue, in one query. A primary still waiting for Venue staff isn't
    shown: attendees see a venue only once it's theirs."""
    # DECISION-PENDING: D70 — approved and primary; otherwise the event's own venue_name / room_number.
    ids = list(event_ids)
    if not ids:
        return {}
    rows = db.execute(
        select(VenueBooking.event_id, Venue)
        .join(Venue, Venue.id == VenueBooking.venue_id)
        .where(
            VenueBooking.event_id.in_(ids),
            VenueBooking.is_primary.is_(True),
            VenueBooking.status == VenueBookingStatus.APPROVED,
        )
    ).all()
    return {event_id: venue for event_id, venue in rows}


def attendee_venue(event: Event, venue: Venue | None) -> tuple[str | None, str | None]:
    """The venue's name and where it is, as attendees see them: the primary venue's name and location,
    or, without one, the event's own venue_name and room_number (both null for an online event)."""
    if venue is not None:
        return venue.name, venue.location
    return event.venue_name, event.room_number
