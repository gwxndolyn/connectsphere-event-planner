"""US9 (SCRUM-12): D93 lets an event cancelled while Approved have no date, capacity or delivery mode. Every read
route must cope, for every role that could reach it (Matt's review of #115). See docs/testing/US9-cancel-event.md."""

import re
from datetime import date, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.equipment.models import TechStaffAssignment
from app.event.models import CancellationStatus, Event, EventCancellation, EventStatus
from app.user.models import User, UserRole
from app.venue.models import VenueBookingStatus
from tests.equipment.test_equipment_reservation_schema import make_approved_line
from tests.factories import NOW, make_attendee, make_event, make_user, make_venue, make_venue_booking
from tests.user.test_role_scope import app_routes

pytestmark = pytest.mark.anyio


@pytest.fixture
def people(db: Session) -> dict[str, User]:
    users = {role.value: make_user(db, role) for role in UserRole}
    attendee = make_attendee(db)
    users["attendee"] = db.get(User, attendee.id)
    return users


@pytest.fixture
def dateless(db: Session, people: dict[str, User]) -> dict[str, str]:
    """An event cancelled while Approved: no date, capacity or delivery mode, with a released venue, an approved
    equipment line, a Tech support assignment and its cancellation record. The ids each route's path takes."""
    coordinator = people["coordinator"]
    event = make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)
    event.created_by_user_id = people["organiser"].id
    event.request_reference = "ER-2026-009999"
    event.preferred_dates = [NOW.date() + timedelta(days=30)]
    event.preferred_start_time, event.preferred_end_time = time(9, 0), time(11, 0)
    event.capacity = None
    event.delivery_mode = None
    db.flush()
    venue = make_venue(db)
    booking = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, status=VenueBookingStatus.APPROVED,
        decided_by_user_id=people["venue_staff"].id,
    )
    line = make_approved_line(db, event)
    db.add(
        TechStaffAssignment(event_id=event.id, staff_user_id=people["tech_support"].id, assigned_by_user_id=coordinator.id)
    )
    event.status = EventStatus.CANCELLED
    booking.status, booking.withdrawn_at = VenueBookingStatus.WITHDRAWN, NOW
    db.add(
        EventCancellation(
            event_id=event.id, requested_by_user_id=coordinator.id, reason="Clash", requested_at=NOW,
            status=CancellationStatus.APPROVED, decided_by_user_id=coordinator.id, decided_at=NOW, direct=True,
        )
    )
    db.flush()
    assert (event.start_at, event.capacity) == (None, None)
    return {
        "venue_id": str(venue.id),
        "booking_id": str(booking.id),
        "line_id": str(line.id),
        "staff_user_id": str(people["tech_support"].id),
        "registration_id": str(event.id),  # no registration: an Approved event never took any
        "default": str(event.id),
    }


def concrete(path: str, ids: dict[str, str]) -> str:
    return re.sub(r"\{([a-z_]+)\}", lambda match: ids.get(match.group(1), ids["default"]), path)


async def test_tc_us9_08_no_read_route_fails_on_an_event_cancelled_before_it_was_planned(
    client: AsyncClient, db: Session, people: dict[str, User], dateless: dict[str, str]
) -> None:
    today = date.fromisoformat(NOW.date().isoformat())
    calendar = f"?from={today.isoformat()}&to={(today + timedelta(days=41)).isoformat()}"
    failures = []
    for method, path in sorted(app_routes()):
        if method != "GET":
            continue
        url = concrete(path, dateless) + (calendar if path.endswith("/calendar") else "")
        for role, user in people.items():
            # Both identity stubs, so attendee routes and user routes each find this person.
            headers = {"X-User-Id": str(user.id), "X-Attendee-Id": str(user.id)}
            response = await client.get(url, headers=headers)
            if response.status_code >= 500:
                failures.append((role, url, response.status_code))

    assert failures == []
