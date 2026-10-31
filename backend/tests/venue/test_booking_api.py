"""US22 venue booking request, PR 2 (SCRUM-112, story SCRUM-89): create, withdraw and list
bookings, their refusals, the Venue Staff notice and US20's inactive-venue gap. The table and its
overlap guard are PR 1's (test_booking_schema.py); see docs/testing/US22-venue-booking.md."""

import threading
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import DeliveryMode, Event, EventStatus
from app.user.models import User, UserRole
from app.venue import booking_service as booking_service_module
from app.venue.booking_service import booking_service
from app.venue.models import Venue, VenueBooking, VenueBookingStatus
from app.venue.schemas import VenueBookingWrite
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_block, make_venue_booking

pytestmark = pytest.mark.anyio

CREATE_URL = "/api/v1/venue-bookings"
PENDING_URL = "/api/v1/venue-bookings/pending"
START = NOW + timedelta(days=7)
END = START + timedelta(hours=2)
# US24 (SCRUM-128): every request says what the venue is for (D66).
REQUIRED = ["event_id", "venue_id", "starts_at", "ends_at", "expected_attendees", "room_layout", "purpose"]
# Every status that isn't bookable and isn't a draft (a draft is 404, D11).
UNBOOKABLE = [
    EventStatus.SUBMITTED,
    EventStatus.UNDER_REVIEW,
    EventStatus.AWAITING_CLARIFICATION,
    EventStatus.REJECTED,
    EventStatus.CONFIRMED,
    EventStatus.CANCELLED,
    EventStatus.COMPLETED,
]


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def withdraw_url(booking_id: uuid.UUID) -> str:
    return f"/api/v1/venue-bookings/{booking_id}/withdraw"


def event_bookings_url(event_id: uuid.UUID) -> str:
    return f"/api/v1/events/{event_id}/venue-bookings"


def booking_body(event: Event, venue: Venue, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "event_id": str(event.id),
        "venue_id": str(venue.id),
        "starts_at": START.isoformat(),
        "ends_at": END.isoformat(),
        "expected_attendees": 30,
        "room_layout": "theatre",
        "purpose": "Main venue",
    }
    body.update(overrides)
    return body


def when(value: str) -> datetime:
    return datetime.fromisoformat(value)


def booking_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(VenueBooking))


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def staff(db: Session) -> User:
        return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def event(db: Session, coordinator: User) -> Event:
    # DECISION-PENDING: D24 — nothing approves a request until US17, so tests create it approved.
    # Assigned to `coordinator` (US10a): only the assigned coordinator may book it (AC 1, D20).
    return make_event(db, name="Data Science Summit", status=EventStatus.APPROVED, coordinator_id=coordinator.id)


@pytest.fixture
def venue(db: Session) -> Venue:
    # Capacity 40; has a projector, no accessibility features, theatre layout only.
    return make_venue(db, name="Hall A")


@pytest.fixture
def plain_venue(db: Session) -> Venue:
    # Hall A with no setup or turnaround (US13), so the TC-US22-09 tests keep proving the plain
    # [) rule; the buffered rule is US13's (test_buffer_schema.py, PR 2's API tests).
    return make_venue(db, name="Hall A", setup_minutes=0, turnaround_minutes=0)


# --- TC-US22-04 create ---


async def test_tc_us22_04_coordinator_requests_a_venue_for_an_approved_event(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(
        CREATE_URL,
        headers=auth(coordinator),
        json=booking_body(
            event,
            venue,
            expected_attendees=35,
            required_facilities=["projector"],
            special_requirements="  Lectern at the front.  ",
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "requested"
    assert body["event"] == {
        "id": str(event.id),
        "name": "Data Science Summit",
        "request_reference": None,
        "status": "approved",
    }
    assert body["venue"] == {"id": str(venue.id), "name": "Hall A", "location": "Stored Building", "capacity": 40}
    assert body["requested_by_user_id"] == str(coordinator.id)
    assert (when(body["starts_at"]), when(body["ends_at"])) == (START, END)
    assert body["expected_attendees"] == 35
    assert body["room_layout"] == "theatre"
    assert body["required_facilities"] == ["projector"]
    assert body["required_accessibility_features"] == []
    assert body["special_requirements"] == "Lectern at the front."
    assert body["withdrawn_at"] is None
    assert body["warnings"] == []
    stored = db.get(VenueBooking, uuid.UUID(body["id"]))
    assert stored.status == VenueBookingStatus.REQUESTED
    assert stored.requested_by_user_id == coordinator.id


# --- TC-US22-05 only Approved or Planning events ---


async def test_tc_us22_05_planning_events_can_be_booked(
    client: AsyncClient, db: Session, coordinator: User, venue: Venue
) -> None:
    # A planned event has its dates; since US24 the window must sit within them (D65).
    event = make_event(db, status=EventStatus.PLANNING, coordinator_id=coordinator.id, start_at=START, end_at=END)

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))

    assert response.status_code == 201


@pytest.mark.parametrize("status", UNBOOKABLE, ids=[status.value for status in UNBOOKABLE])
async def test_tc_us22_05_other_statuses_are_not_bookable(
    client: AsyncClient, db: Session, coordinator: User, venue: Venue, status: EventStatus
) -> None:
    event = make_event(db, status=status, coordinator_id=coordinator.id)

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))

    assert response.status_code == 409
    assert response.json() == {"code": "EVENT_NOT_BOOKABLE", "status": status.value}
    assert booking_count(db) == 0


async def test_tc_us22_05_a_draft_is_not_found(client: AsyncClient, db: Session, coordinator: User, venue: Venue) -> None:
    """D11: a draft is owner-only, so a 409 would reveal that it exists."""
    event = make_event(db, status=EventStatus.DRAFT, coordinator_id=coordinator.id)

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}


# --- TC-US22-06 who may book ---


@pytest.mark.parametrize("role", [UserRole.ORGANISER, UserRole.ATTENDEE, UserRole.VENUE_STAFF])
async def test_tc_us22_06_only_coordinators_may_request(
    client: AsyncClient, db: Session, event: Event, venue: Venue, role: UserRole
) -> None:
    response = await client.post(CREATE_URL, headers=auth(make_user(db, role)), json=booking_body(event, venue))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert booking_count(db) == 0


async def test_tc_us22_06_inactive_coordinator_is_refused(
    client: AsyncClient, db: Session, event: Event, venue: Venue
) -> None:
    inactive = make_user(db, UserRole.COORDINATOR, active=False)

    response = await client.post(CREATE_URL, headers=auth(inactive), json=booking_body(event, venue))

    assert response.status_code == 403


async def test_tc_us22_06_the_assigned_coordinator_may_book_and_list(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    # DECISION-PENDING: D20 — US10a (SCRUM-13) assigns the coordinator; AC 1 lets only them book.
    assert event.coordinator_id == coordinator.id

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))
    listed = await client.get(event_bookings_url(event.id), headers=auth(coordinator))

    assert response.status_code == 201
    assert [row["id"] for row in listed.json()["bookings"]] == [response.json()["id"]]


async def test_tc_us22_06_a_coordinator_not_assigned_to_the_event_is_refused(
    client: AsyncClient, db: Session, event: Event, venue: Venue
) -> None:
    """Someone else's event is 404, never 403, as everywhere else: it isn't theirs to see."""
    other = make_user(db, UserRole.COORDINATOR)

    response = await client.post(CREATE_URL, headers=auth(other), json=booking_body(event, venue))
    listed = await client.get(event_bookings_url(event.id), headers=auth(other))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}
    assert listed.status_code == 404
    assert booking_count(db) == 0


async def test_tc_us22_06_an_unassigned_event_cannot_be_booked(
    client: AsyncClient, db: Session, coordinator: User, staff: User, venue: Venue
) -> None:
    """Approved but not yet assigned (no Lead has picked a coordinator): no coordinator may book it."""
    unassigned = make_event(db, status=EventStatus.APPROVED)

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(unassigned, venue))
    listed = await client.get(event_bookings_url(unassigned.id), headers=auth(coordinator))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}
    assert listed.status_code == 404
    assert booking_count(db) == 0
    # Venue Staff still read any event's bookings.
    assert (await client.get(event_bookings_url(unassigned.id), headers=auth(staff))).status_code == 200


@pytest.mark.parametrize("role", [UserRole.ORGANISER, UserRole.ATTENDEE])
async def test_tc_us22_06_others_cannot_read_booking_lists(
    client: AsyncClient, db: Session, event: Event, role: UserRole
) -> None:
    user = make_user(db, role)

    assert (await client.get(PENDING_URL, headers=auth(user))).status_code == 403
    # Since US24 (D71) an Organiser may read their own event's venues, so another's is 404, not 403.
    expected = 404 if role == UserRole.ORGANISER else 403
    assert (await client.get(event_bookings_url(event.id), headers=auth(user))).status_code == expected


async def test_tc_us22_06_coordinators_cannot_read_the_pending_list(
    client: AsyncClient, coordinator: User
) -> None:
    response = await client.get(PENDING_URL, headers=auth(coordinator))

    assert response.status_code == 403


# --- TC-US22-07 missing and invalid fields ---


async def test_tc_us22_07_missing_fields_are_listed(client: AsyncClient, db: Session, coordinator: User) -> None:
    response = await client.post(CREATE_URL, headers=auth(coordinator), json={})

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": REQUIRED}


@pytest.mark.parametrize("field", REQUIRED)
async def test_tc_us22_07_each_required_field_is_named(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue, field: str
) -> None:
    body = booking_body(event, venue)
    del body[field]

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=body)

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": [field]}


@pytest.mark.parametrize(
    ("overrides", "fields"),
    [
        ({"ends_at": START.isoformat()}, ["ends_at"]),
        ({"ends_at": (START - timedelta(hours=1)).isoformat()}, ["ends_at"]),
        (
            {"starts_at": (NOW - timedelta(minutes=1)).isoformat(), "ends_at": (NOW + timedelta(hours=1)).isoformat()},
            ["starts_at"],
        ),
        ({"starts_at": "2026-10-08T10:00:00", "ends_at": "2026-10-08T12:00:00"}, ["starts_at", "ends_at"]),
        ({"expected_attendees": 0}, ["expected_attendees"]),
        ({"room_layout": "amphitheatre"}, ["room_layout"]),
        ({"required_facilities": ["projector", "jacuzzi"]}, ["required_facilities"]),
        ({"required_accessibility_features": ["ramp"]}, ["required_accessibility_features"]),
        ({"expected_attendees": 0, "room_layout": "amphitheatre"}, ["expected_attendees", "room_layout"]),
    ],
    ids=[
        "ends when it starts",
        "ends before it starts",
        "starts in the past",
        "no timezone offset",
        "no attendees",
        "unknown layout",
        "unknown facility",
        "unknown accessibility feature",
        "every invalid field at once",
    ],
)
async def test_tc_us22_07_invalid_values_are_refused(
    client: AsyncClient,
    db: Session,
    coordinator: User,
    event: Event,
    venue: Venue,
    overrides: dict[str, object],
    fields: list[str],
) -> None:
    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue, **overrides))

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_BOOKING"
    assert response.json()["fields"] == fields
    assert set(response.json()["errors"]) == set(fields)
    assert booking_count(db) == 0


async def test_tc_us22_07_an_unknown_tag_is_named_in_the_message(
    client: AsyncClient, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(
        CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue, required_facilities=["jacuzzi"])
    )

    assert "jacuzzi" in response.json()["errors"]["required_facilities"]


async def test_tc_us22_07_tags_are_trimmed_deduplicated_and_ordered(
    client: AsyncClient, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(
        CREATE_URL,
        headers=auth(coordinator),
        json=booking_body(event, venue, required_facilities=[" wifi", "projector", "wifi "]),
    )

    assert response.status_code == 201
    assert response.json()["required_facilities"] == ["projector", "wifi"]


# --- TC-US22-08 capacity ---


async def test_tc_us22_08_attendance_above_capacity_is_refused(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(
        CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue, expected_attendees=41)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VENUE_CAPACITY_EXCEEDED"
    assert response.json()["fields"] == ["expected_attendees"]
    assert response.json()["capacity"] == 40
    assert "40" in response.json()["message"]
    assert booking_count(db) == 0


async def test_tc_us22_08_attendance_equal_to_capacity_is_accepted(
    client: AsyncClient, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(
        CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue, expected_attendees=40)
    )

    assert response.status_code == 201


# --- TC-US22-09 overlap ---


@pytest.mark.parametrize("existing", [VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED])
async def test_tc_us22_09_overlapping_window_is_refused_with_the_conflict(
    client: AsyncClient, db: Session, coordinator: User, event: Event, plain_venue: Venue, existing: VenueBookingStatus
) -> None:
    # D21 (decided): Requested blocks as well as Approved.
    make_venue_booking(
        db, event=event, venue=plain_venue, user=make_user(db, UserRole.COORDINATOR), status=existing
    )

    response = await client.post(
        CREATE_URL,
        headers=auth(coordinator),
        json=booking_body(
            event,
            plain_venue,
            starts_at=(START + timedelta(hours=1)).isoformat(),
            ends_at=(END + timedelta(hours=1)).isoformat(),
        ),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_UNAVAILABLE"
    conflict = response.json()["conflict"]
    assert (when(conflict["starts_at"]), when(conflict["ends_at"])) == (START, END)
    assert response.json()["message"]
    assert booking_count(db) == 1


async def test_tc_us22_09_one_second_overlap_is_refused(
    client: AsyncClient, db: Session, coordinator: User, event: Event, plain_venue: Venue
) -> None:
    make_venue_booking(db, event=event, venue=plain_venue, user=coordinator)

    response = await client.post(
        CREATE_URL,
        headers=auth(coordinator),
        json=booking_body(
            event,
            plain_venue,
            starts_at=(END - timedelta(seconds=1)).isoformat(),
            ends_at=(END + timedelta(hours=1)).isoformat(),
        ),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_UNAVAILABLE"


async def test_tc_us22_09_back_to_back_is_accepted(
    client: AsyncClient, db: Session, coordinator: User, event: Event, plain_venue: Venue
) -> None:
    make_venue_booking(db, event=event, venue=plain_venue, user=coordinator)

    response = await client.post(
        CREATE_URL,
        headers=auth(coordinator),
        json=booking_body(event, plain_venue, starts_at=END.isoformat(), ends_at=(END + timedelta(hours=1)).isoformat()),
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    ("block_starts", "block_ends"),
    [
        (START + timedelta(hours=1), END + timedelta(hours=1)),
        (END - timedelta(seconds=1), END + timedelta(hours=1)),
        (START - timedelta(hours=1), START + timedelta(seconds=1)),
    ],
    ids=["overlapping", "one second into the end", "one second into the start"],
)
async def test_tc_us22_09_a_window_overlapping_a_venue_block_is_refused(
    client: AsyncClient,
    db: Session,
    notifier: FakeNotifier,
    coordinator: User,
    staff: User,
    event: Event,
    plain_venue: Venue,
    block_starts: datetime,
    block_ends: datetime,
) -> None:
    """AC 3's unavailability period: US2's venue_blocks, the same [) rule as bookings."""
    make_venue_block(db, plain_venue, block_starts, block_ends, note="Maintenance")

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, plain_venue))

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_UNAVAILABLE"
    conflict = response.json()["conflict"]
    assert (when(conflict["starts_at"]), when(conflict["ends_at"])) == (block_starts, block_ends)
    assert "unavailable" in response.json()["message"]
    assert booking_count(db) == 0
    assert notifier.venue_bookings == []


async def test_tc_us22_09_back_to_back_with_a_venue_block_is_accepted(
    client: AsyncClient, db: Session, coordinator: User, event: Event, plain_venue: Venue
) -> None:
    make_venue_block(db, plain_venue, START - timedelta(hours=1), START)
    make_venue_block(db, plain_venue, END, END + timedelta(hours=1))

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, plain_venue))

    assert response.status_code == 201


async def test_tc_us22_09_a_block_at_another_venue_does_not_count(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    make_venue_block(db, make_venue(db, name="Hall B"), START, END)

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))

    assert response.status_code == 201


# --- TC-US22-10 warnings ---


async def test_tc_us22_10_missing_facilities_and_layout_warn_but_save(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(
        CREATE_URL,
        headers=auth(coordinator),
        json=booking_body(
            event,
            venue,
            room_layout="classroom",
            purpose="Main venue",
            required_facilities=["wifi", "projector", "stage"],
            required_accessibility_features=["wheelchair"],
        ),
    )

    assert response.status_code == 201
    warnings = response.json()["warnings"]
    assert [(warning["field"], warning["item"]) for warning in warnings] == [
        ("required_facilities", "stage"),
        ("required_facilities", "wifi"),
        ("required_accessibility_features", "wheelchair"),
        ("room_layout", "classroom"),
    ]
    assert all(warning["message"] for warning in warnings)
    assert booking_count(db) == 1


async def test_tc_us22_10_a_venue_with_everything_has_no_warnings(
    client: AsyncClient, coordinator: User, event: Event, venue: Venue
) -> None:
    response = await client.post(
        CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue, required_facilities=["projector"])
    )

    assert response.status_code == 201
    assert response.json()["warnings"] == []


# --- TC-US22-11 inactive venue ---


async def test_tc_us22_11_an_inactive_venue_cannot_be_requested(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    venue = make_venue(db, is_active=False)

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}
    assert booking_count(db) == 0


# --- TC-US22-12 the pending list and the event's bookings ---


async def test_tc_us22_12_new_request_shows_in_both_lists(
    client: AsyncClient, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    created = (await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))).json()

    pending = await client.get(PENDING_URL, headers=auth(staff))
    assert pending.status_code == 200
    [row] = [row for row in pending.json()["bookings"] if row["id"] == created["id"]]
    assert row["event"]["name"] == "Data Science Summit"
    assert row["venue"]["name"] == "Hall A"
    assert row["status"] == "requested"
    assert "warnings" not in row

    for reader in (coordinator, staff):
        listed = await client.get(event_bookings_url(event.id), headers=auth(reader))
        assert listed.status_code == 200
        assert [row["id"] for row in listed.json()["bookings"]] == [created["id"]]


async def test_tc_us22_12_pending_list_holds_requested_only_oldest_first(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    other = make_venue(db, name="Hall B")
    older = make_venue_booking(db, event=event, venue=venue, user=coordinator, created_at=NOW - timedelta(days=2))
    newer = make_venue_booking(db, event=event, venue=other, user=coordinator, created_at=NOW - timedelta(days=1))
    for status, offset in ((VenueBookingStatus.APPROVED, 1), (VenueBookingStatus.WITHDRAWN, 2), (VenueBookingStatus.REJECTED, 3)):
        make_venue_booking(
            db,
            event=event,
            venue=venue,
            user=coordinator,
            status=status,
            starts_at=END + timedelta(days=offset),
        )

    response = await client.get(PENDING_URL, headers=auth(staff))

    assert [row["id"] for row in response.json()["bookings"]] == [str(older.id), str(newer.id)]


async def test_tc_us22_12_event_list_shows_every_status_by_start(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    later = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, status=VenueBookingStatus.WITHDRAWN, starts_at=END + timedelta(days=1)
    )
    sooner = make_venue_booking(db, event=event, venue=venue, user=coordinator)
    make_venue_booking(db, event=make_event(db, status=EventStatus.APPROVED), venue=venue, user=coordinator, starts_at=END + timedelta(days=2))

    response = await client.get(event_bookings_url(event.id), headers=auth(coordinator))

    assert [row["id"] for row in response.json()["bookings"]] == [str(sooner.id), str(later.id)]


async def test_tc_us22_12_a_drafts_bookings_are_not_found(
    client: AsyncClient, db: Session, coordinator: User
) -> None:
    draft = make_event(db, status=EventStatus.DRAFT, coordinator_id=coordinator.id)

    response = await client.get(event_bookings_url(draft.id), headers=auth(coordinator))

    assert response.status_code == 404


# --- TC-US22-13 withdraw ---


async def test_tc_us22_13_withdrawing_frees_the_window(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    created = (await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))).json()

    response = await client.post(withdraw_url(uuid.UUID(created["id"])), headers=auth(coordinator))

    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"
    assert when(response.json()["withdrawn_at"]) == NOW
    again = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))
    assert again.status_code == 201


# Since US24 (SCRUM-128, D69) an approved booking can be withdrawn too (TC-US24-16); only a rejected or
# already withdrawn one can't.
@pytest.mark.parametrize("status", [VenueBookingStatus.REJECTED, VenueBookingStatus.WITHDRAWN])
async def test_tc_us22_13_only_a_pending_request_can_be_withdrawn(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue, status: VenueBookingStatus
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, status=status)

    response = await client.post(withdraw_url(booking.id), headers=auth(coordinator))

    assert response.status_code == 409
    # Since US24 (#100 review): approved can be withdrawn too (D69), so the refusal says it isn't live.
    assert response.json() == {"code": "BOOKING_NOT_LIVE", "status": status.value}
    db.expire_all()
    assert db.get(VenueBooking, booking.id).status == status


async def test_tc_us22_13_another_coordinator_cannot_withdraw_it(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator)

    response = await client.post(withdraw_url(booking.id), headers=auth(make_user(db, UserRole.COORDINATOR)))

    assert response.status_code == 404
    db.expire_all()
    assert db.get(VenueBooking, booking.id).status == VenueBookingStatus.REQUESTED


async def test_tc_us22_13_venue_staff_cannot_withdraw_it(
    client: AsyncClient, db: Session, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator)

    response = await client.post(withdraw_url(booking.id), headers=auth(staff))

    assert response.status_code == 403


# --- TC-US22-14 Venue Staff are notified ---


async def test_tc_us22_14_each_active_staff_member_is_notified_once(
    client: AsyncClient, db: Session, notifier: FakeNotifier, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    second = make_user(db, UserRole.VENUE_STAFF)
    make_user(db, UserRole.VENUE_STAFF, active=False)

    created = (await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))).json()

    assert sorted(call["email"] for call in notifier.venue_bookings) == sorted([staff.email, second.email])
    for call in notifier.venue_bookings:
        assert call["booking_id"] == uuid.UUID(created["id"])
        assert call["event_name"] == "Data Science Summit"
        assert call["venue_name"] == "Hall A"
        assert (call["starts_at"], call["ends_at"]) == (START, END)


async def test_tc_us22_14_a_refused_request_notifies_nobody(
    client: AsyncClient, db: Session, notifier: FakeNotifier, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    for body in (
        booking_body(event, venue, expected_attendees=41),
        booking_body(event, venue, room_layout="amphitheatre"),
        {},
    ):
        response = await client.post(CREATE_URL, headers=auth(coordinator), json=body)
        assert response.status_code == 422

    make_venue_booking(db, event=event, venue=venue, user=coordinator)
    assert (await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))).status_code == 409

    assert notifier.venue_bookings == []


async def test_tc_us22_14_a_notifier_failure_keeps_the_booking(
    client: AsyncClient, db: Session, notifier: FakeNotifier, coordinator: User, staff: User, event: Event, venue: Venue
) -> None:
    notifier.fail = True

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))

    assert response.status_code == 201
    assert booking_count(db) == 1


async def test_tc_us22_14_an_unnamed_event_is_named_by_its_reference(
    client: AsyncClient, db: Session, notifier: FakeNotifier, coordinator: User, staff: User, venue: Venue
) -> None:
    """An approved request may have no name yet (events_final_fields_required)."""
    event = Event(
        status=EventStatus.APPROVED,
        request_reference="ER-2026-000042",
        delivery_mode=DeliveryMode.IN_PERSON,
        coordinator_id=coordinator.id,
    )
    db.add(event)
    db.flush()

    response = await client.post(CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue))

    assert response.status_code == 201
    assert [call["event_name"] for call in notifier.venue_bookings] == ["ER-2026-000042"]


# --- TC-US22-15 two requests at the same moment ---


class Committed:
    """Rows committed for real, so separate sessions (connections) can all see them."""

    def __init__(
        self, coordinators: list[uuid.UUID], staff: uuid.UUID, events: dict[uuid.UUID, uuid.UUID], venue: uuid.UUID
    ) -> None:
        # events: each coordinator's own assigned event (US10a), all to be held at the same venue.
        self.coordinators, self.staff, self.events, self.venue = coordinators, staff, events, venue

    def body(self, event: uuid.UUID, offset: timedelta = timedelta()) -> VenueBookingWrite:
        return VenueBookingWrite(
            event_id=event,
            venue_id=self.venue,
            starts_at=START + offset,
            ends_at=END + offset,
            expected_attendees=20,
            room_layout="theatre",
            purpose="Main venue",
        )

    def request(self, engine: Engine, coordinator: uuid.UUID, notifier: FakeNotifier, offset: timedelta) -> object:
        """One request in its own session: 201, or the refusal's (status, code)."""
        with Session(engine) as session:
            try:
                body = self.body(self.events[coordinator], offset)
                booking_service.create(session, session.get(User, coordinator), body, NOW, notifier)
                return 201
            except DomainError as error:
                return (error.status_code, error.code)


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    """The `db` fixture's rows live in one uncommitted transaction, invisible to other connections,
    so these tests commit their own and delete them afterwards."""
    with Session(engine) as setup:
        coordinators = [User(email=f"{uuid.uuid4().hex}@smu.edu.sg", roles=[UserRole.COORDINATOR]) for _ in range(2)]
        staff = User(email=f"{uuid.uuid4().hex}@smu.edu.sg", roles=[UserRole.VENUE_STAFF])
        setup.add_all([*coordinators, staff])
        setup.flush()
        # AC 7: two coordinators, each requesting for the event assigned to them, at one venue.
        events = {
            user.id: make_event(setup, status=EventStatus.APPROVED, coordinator_id=user.id).id for user in coordinators
        }
        venue = make_venue(setup)
        setup.commit()
        rows = Committed([user.id for user in coordinators], staff.id, events, venue.id)
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(VenueBooking).where(VenueBooking.venue_id == rows.venue))
            cleanup.execute(delete(Venue).where(Venue.id == rows.venue))
            cleanup.execute(delete(Event).where(Event.id.in_(list(rows.events.values()))))
            cleanup.execute(delete(User).where(User.id.in_([*rows.coordinators, rows.staff])))
            cleanup.commit()


def test_tc_us22_15_simultaneous_overlapping_requests_only_the_first_wins(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real race: two sessions on separate connections both pass the overlap pre-check (held at a
    barrier), then insert. The database refuses one: the exclusion constraint once the winner commits,
    or, now and then, a deadlock between the two inserts followed by one retry."""
    barrier = threading.Barrier(2, timeout=10)
    held = threading.local()
    # Since US13 PR 2 the pre-check is availability.evaluate_window, as booking_service imports it.
    original = booking_service_module.evaluate_window
    lookups: list[object] = []

    def evaluate_then_wait(*args: object, **kwargs: object) -> object:
        evaluation = original(*args, **kwargs)
        # The first clashing booking each look found, or None: what the US22 pre-check returned.
        lookups.append(next((c for c in evaluation.conflicts if c.kind == "booking"), None))
        if not getattr(held, "done", False):  # only the first pre-check waits, not later lookups
            held.done = True
            barrier.wait()
        return evaluation

    monkeypatch.setattr(booking_service_module, "evaluate_window", evaluate_then_wait)
    notifier = FakeNotifier()
    outcomes: list[object] = []
    threads = [
        threading.Thread(
            target=lambda user=user, offset=offset: outcomes.append(committed.request(engine, user, notifier, offset))
        )
        for user, offset in zip(committed.coordinators, (timedelta(), timedelta(minutes=30)))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(outcomes) == 2
    assert outcomes.count(201) == 1
    assert outcomes.count((409, "VENUE_UNAVAILABLE")) == 1
    # Both pre-checks found nothing, so the database made the refusal; the loser's last lookup found
    # the winner's window to report.
    assert lookups[:2] == [None, None]
    assert lookups[-1] is not None
    with Session(engine) as check:
        assert check.scalar(select(func.count()).where(VenueBooking.venue_id == committed.venue)) == 1
    assert len(notifier.venue_bookings) == 1


class Deadlock:
    sqlstate = "40P01"


def deadlock_on_first_commits(monkeypatch: pytest.MonkeyPatch, times: int) -> None:
    """Makes the first `times` commits fail as Postgres's deadlock victim would."""
    original = booking_service_module.VenueBookingService._commit
    remaining = [times]

    def commit(self, db: Session, *args: object) -> None:
        if remaining[0]:
            remaining[0] -= 1
            raise OperationalError("INSERT INTO venue_bookings ...", {}, Deadlock())
        original(self, db, *args)

    monkeypatch.setattr(booking_service_module.VenueBookingService, "_commit", commit)


def test_tc_us22_15_a_deadlock_victim_tries_once_more(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The race's rarer path, forced: the request chosen as deadlock victim runs again rather than
    failing with a 500."""
    deadlock_on_first_commits(monkeypatch, 1)
    notifier = FakeNotifier()

    assert committed.request(engine, committed.coordinators[0], notifier, timedelta()) == 201
    assert len(notifier.venue_bookings) == 1


def test_tc_us22_15_a_second_deadlock_is_refused_as_unavailable(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    deadlock_on_first_commits(monkeypatch, 2)
    notifier = FakeNotifier()

    assert committed.request(engine, committed.coordinators[0], notifier, timedelta()) == (409, "VENUE_UNAVAILABLE")
    assert notifier.venue_bookings == []


# --- TC-US22-16 US20's inactive-venue gap ---


async def test_tc_us22_16_the_events_coordinator_can_read_a_deactivated_venue(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    """D20 after US10a: the coordinator assigned to the booked event, even if someone else (e.g. the
    coordinator before a reassignment) made the request."""
    venue = make_venue(db, name="Closed Hall")
    make_venue_booking(db, event=event, venue=venue, user=make_user(db, UserRole.COORDINATOR))
    venue.is_active = False
    db.flush()

    response = await client.get(f"/api/v1/venues/{venue.id}", headers=auth(coordinator))

    assert response.status_code == 200
    assert response.json()["name"] == "Closed Hall"
    assert response.json()["is_active"] is False


async def test_tc_us22_16_everyone_else_still_gets_not_found(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    venue = make_venue(db, is_active=False)
    # The live booking is on `event` (assigned to `coordinator`), requested by someone not assigned.
    requester = make_user(db, UserRole.COORDINATOR)
    make_venue_booking(db, event=event, venue=venue, user=requester)
    # Another coordinator's event has only a withdrawn booking here.
    withdrawn_only = make_user(db, UserRole.COORDINATOR)
    make_venue_booking(
        db,
        event=make_event(db, status=EventStatus.APPROVED, coordinator_id=withdrawn_only.id),
        venue=venue,
        user=withdrawn_only,
        status=VenueBookingStatus.WITHDRAWN,
        starts_at=END + timedelta(days=1),
    )

    for reader in (
        requester,
        withdrawn_only,
        make_user(db, UserRole.COORDINATOR),
        make_user(db, UserRole.ORGANISER),
        make_user(db, UserRole.ATTENDEE),
    ):
        response = await client.get(f"/api/v1/venues/{venue.id}", headers=auth(reader))
        assert response.status_code == 404, reader.email


async def test_tc_us22_16_the_venue_still_leaves_the_coordinators_list(
    client: AsyncClient, db: Session, coordinator: User, event: Event
) -> None:
    venue = make_venue(db, name="Closed Hall", is_active=False)
    make_venue_booking(db, event=event, venue=venue, user=coordinator)

    response = await client.get("/api/v1/venues", headers=auth(coordinator))

    assert "Closed Hall" not in [row["name"] for row in response.json()["venues"]]


# --- TC-US22-17 no buffer overrides ---


@pytest.mark.parametrize("field", ["setup_minutes", "turnaround_minutes"])
async def test_tc_us22_17_a_booking_cannot_override_the_buffers(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue, field: str
) -> None:
    response = await client.post(
        CREATE_URL, headers=auth(coordinator), json=booking_body(event, venue, **{field: 0})
    )

    assert response.status_code == 422
    assert booking_count(db) == 0


# --- TC-US22-18 identity and unknown ids ---


async def test_tc_us22_18_every_route_needs_an_identity(client: AsyncClient, event: Event) -> None:
    for method, url in (
        ("POST", CREATE_URL),
        ("POST", withdraw_url(uuid.uuid4())),
        ("GET", PENDING_URL),
        ("GET", event_bookings_url(event.id)),
    ):
        response = await client.request(method, url, json={} if method == "POST" else None)
        assert response.status_code == 401, url
        assert response.json()["code"] == "UNAUTHENTICATED"


async def test_tc_us22_18_unknown_ids_are_not_found(
    client: AsyncClient, db: Session, coordinator: User, event: Event, venue: Venue
) -> None:
    unknown = uuid.uuid4()

    for body in (
        booking_body(event, venue, event_id=str(unknown)),
        booking_body(event, venue, venue_id=str(unknown)),
    ):
        response = await client.post(CREATE_URL, headers=auth(coordinator), json=body)
        assert response.status_code == 404
        assert response.json() == {"code": "NOT_FOUND"}
    assert (await client.post(withdraw_url(unknown), headers=auth(coordinator))).status_code == 404
    assert (await client.get(event_bookings_url(unknown), headers=auth(coordinator))).status_code == 404
