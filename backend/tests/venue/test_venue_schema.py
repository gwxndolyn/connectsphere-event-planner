"""US20 venue catalogue, PR 1 (SCRUM-87): the `venues` table, its constraints and the seed.
The API checks for the same ACs come in PR 2; see docs/testing/US20-venue-catalogue.md."""

from datetime import time

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event
from app.seed import VENUES, seed, seed_id
from app.user.models import User, UserRole
from app.venue.models import ACCESSIBILITY_FEATURES, FACILITIES, ROOM_LAYOUTS, Venue
from tests.factories import NOW

AGREED_COLUMNS = {
    "id",
    "name",
    "location",
    "capacity",
    "facilities",
    "accessibility_features",
    "room_layouts",
    "opens_at",
    "closes_at",
    "setup_minutes",
    "turnaround_minutes",
    "is_active",
}


def valid_venue(**overrides) -> Venue:
    fields = {
        "name": "Test Seminar Room",
        "location": "Test Building, Level 1",
        "capacity": 30,
        "facilities": ["projector", "wifi"],
        "accessibility_features": ["wheelchair"],
        "room_layouts": ["classroom"],
        "opens_at": time(9, 0),
        "closes_at": time(18, 0),
        "setup_minutes": 15,
        "turnaround_minutes": 10,
    }
    return Venue(**(fields | overrides))


def test_tc_us20_01_a_venue_with_every_field_round_trips(db: Session) -> None:
    venue = valid_venue()
    db.add(venue)
    db.flush()
    db.expire(venue)

    stored = db.get(Venue, venue.id)
    assert stored.name == "Test Seminar Room"
    assert stored.location == "Test Building, Level 1"
    assert stored.capacity == 30
    assert stored.facilities == ["projector", "wifi"]
    assert stored.accessibility_features == ["wheelchair"]
    assert stored.room_layouts == ["classroom"]
    assert (stored.opens_at, stored.closes_at) == (time(9, 0), time(18, 0))
    assert (stored.setup_minutes, stored.turnaround_minutes) == (15, 10)
    assert stored.is_active is True


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"capacity": 0}, "venues_capacity_positive"),
        ({"capacity": -5}, "venues_capacity_positive"),
        ({"setup_minutes": -1}, "venues_setup_minutes_non_negative"),
        ({"turnaround_minutes": -1}, "venues_turnaround_minutes_non_negative"),
        ({"opens_at": time(9, 0), "closes_at": time(9, 0)}, "venues_hours_valid"),
        ({"opens_at": time(18, 0), "closes_at": time(9, 0)}, "venues_hours_valid"),
        ({"name": "   "}, "venues_name_not_blank"),
        ({"location": ""}, "venues_location_not_blank"),
        ({"facilities": ["projector", "jacuzzi"]}, "venues_facilities_known"),
        ({"accessibility_features": ["ramp"]}, "venues_accessibility_features_known"),
        ({"room_layouts": ["amphitheatre"]}, "venues_room_layouts_known"),
    ],
    ids=[
        "capacity 0",
        "negative capacity",
        "negative setup",
        "negative turnaround",
        "closes when it opens",
        "closes before it opens",
        "blank name",
        "blank location",
        "unknown facility",
        "unknown accessibility feature",
        "unknown layout",
    ],
)
def test_tc_us20_04_database_rejects_invalid_venues(db: Session, overrides: dict, constraint: str) -> None:
    """Each rule has its own named CHECK, which PR 2 turns into an error naming the field."""
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            db.add(valid_venue(**overrides))
            db.flush()

    assert raised.value.orig.diag.constraint_name == constraint


def test_tc_us20_04_zero_minute_buffers_are_valid(db: Session) -> None:
    venue = valid_venue(setup_minutes=0, turnaround_minutes=0)
    db.add(venue)
    db.flush()

    assert (venue.setup_minutes, venue.turnaround_minutes) == (0, 0)


def test_tc_us20_07_buffers_exist_only_on_venues(engine) -> None:
    """AC 7: setup and turnaround are set per venue, so no other table (a booking, later) has them."""
    inspector = inspect(engine)
    tables_with_buffers = {
        table
        for table in inspector.get_table_names()
        if {"setup_minutes", "turnaround_minutes"} & {column["name"] for column in inspector.get_columns(table)}
    }

    assert tables_with_buffers == {"venues"}


def test_tc_us20_08_venue_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("venues")} == AGREED_COLUMNS
    assert {constraint["name"] for constraint in inspector.get_check_constraints("venues")} == {
        "venues_name_not_blank",
        "venues_location_not_blank",
        "venues_capacity_positive",
        "venues_hours_valid",
        "venues_setup_minutes_non_negative",
        "venues_turnaround_minutes_non_negative",
        "venues_facilities_known",
        "venues_accessibility_features_known",
        "venues_room_layouts_known",
    }
    assert db.execute(text("select relrowsecurity from pg_class where oid = 'venues'::regclass")).scalar_one() is True


def test_tc_us20_09_seed_gives_us2_varied_venues(db: Session) -> None:
    seed(db, now=NOW)
    seeded_ids = [seed_id("venue", spec.slug) for spec in VENUES]
    venues = list(db.scalars(select(Venue).where(Venue.id.in_(seeded_ids))))

    assert len(venues) == 6
    inactive = [venue for venue in venues if not venue.is_active]
    assert len(inactive) == 1
    # No seeded event sits at the deactivated venue, so demos never show one.
    event_rooms = {room for room in db.scalars(select(Event.room_number)) if room}
    assert not any(room in inactive[0].name for room in event_rooms)
    assert any(venue.setup_minutes == 0 and venue.turnaround_minutes == 0 for venue in venues)
    assert len({venue.capacity for venue in venues}) >= 3
    for venue in venues:
        for tags, allowed in (
            (venue.facilities, FACILITIES),
            (venue.accessibility_features, ACCESSIBILITY_FEATURES),
            (venue.room_layouts, ROOM_LAYOUTS),
        ):
            assert set(tags) <= set(allowed), venue.name
            assert len(tags) == len(set(tags)), f"duplicate tag on {venue.name}"

    # Idempotent: a second run updates the same rows and adds none.
    count_before = len(list(db.scalars(select(Venue.id))))
    seed(db, now=NOW)
    assert len(list(db.scalars(select(Venue.id)))) == count_before


def test_tc_us20_09_seed_has_a_venue_staff_user(db: Session) -> None:
    # DECISION-PENDING: D19 — operations_manager stands in for Venue Staff until US16b (PR 2).
    seed(db, now=NOW)

    staff = db.get(User, seed_id("user", "venue-staff"))
    assert staff is not None
    assert staff.role == UserRole.OPERATIONS_MANAGER
    assert staff.is_active is True
