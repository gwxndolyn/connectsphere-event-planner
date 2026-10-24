"""US13 setup and turnaround buffers, PR 1 (SCRUM-114, story SCRUM-16): each booking stores its
occupied window [start - setup, end + turnaround), the overlap guard covers it, and bookings get a
reference. The API checks (hours, overlap details, the reusable rule) come in PR 2; see
docs/testing/US13-buffers.md."""

import re
import uuid
from collections.abc import Generator
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.seed import VENUE_BOOKINGS, seed, seed_id
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBooking, VenueBookingStatus, occupied_window
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

REVISION = "20261024_1200_us13_buffers"
PREVIOUS_REVISION = "20261025_1200_us26_equipment"  # US13 follows US26 since #63 merged
NO_OVERLAP = "venue_bookings_no_overlap"
SINGAPORE = ZoneInfo("Asia/Singapore")
DAY = (NOW + timedelta(days=7)).date()


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime.combine(DAY, time(hour, minute, second), SINGAPORE)


@pytest.fixture
def event(db: Session) -> Event:
    # DECISION-PENDING: D24 — nothing approves a request until US17, so tests create it approved.
    return make_event(db, status=EventStatus.APPROVED)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def venue(db: Session) -> Venue:
    # AC 2's example buffers: 30 minutes' setup, 45 minutes' turnaround.
    return make_venue(db, setup_minutes=30, turnaround_minutes=45)


def refused_constraint(db: Session, **booking: object) -> str:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_venue_booking(db, **booking)
    return raised.value.orig.diag.constraint_name


# --- TC-US13-01 schema ---


def test_tc_us13_01_bookings_store_an_occupied_window_and_a_reference(db: Session, engine: Engine) -> None:
    columns = {column["name"]: column for column in inspect(engine).get_columns("venue_bookings")}

    for name in ("occupied_starts_at", "occupied_ends_at", "reference"):
        assert columns[name]["nullable"] is False, name
    assert {constraint["name"] for constraint in inspect(engine).get_check_constraints("venue_bookings")} >= {
        "venue_bookings_occupied_covers_window"
    }
    unique = {tuple(constraint["column_names"]) for constraint in inspect(engine).get_unique_constraints("venue_bookings")}
    assert ("reference",) in unique
    definition = db.scalar(text("select pg_get_constraintdef(oid) from pg_constraint where conname = :name"), {"name": NO_OVERLAP})
    assert "tstzrange(occupied_starts_at, occupied_ends_at, '[)'::text)" in definition
    assert "requested" in definition and "approved" in definition
    assert db.execute(text("select relrowsecurity from pg_class where oid = 'venue_bookings'::regclass")).scalar_one() is True


def test_tc_us13_01_buffers_still_belong_to_the_venue_only(engine: Engine) -> None:
    """The booking stores the window the buffers produce, never the buffers (US20 AC 7, CR-01)."""
    columns = {column["name"] for column in inspect(engine).get_columns("venue_bookings")}

    assert not {"setup_minutes", "turnaround_minutes"} & columns


def test_tc_us13_01_an_occupied_window_narrower_than_the_booking_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    constraint = refused_constraint(
        db,
        event=event,
        venue=venue,
        user=coordinator,
        starts_at=at(10),
        ends_at=at(12),
        occupied_starts_at=at(10, 15),
        occupied_ends_at=at(12),
    )

    assert constraint == "venue_bookings_occupied_covers_window"


def test_tc_us13_01_the_seed_stores_each_bookings_occupied_window(db: Session) -> None:
    seed(db, now=NOW)

    for spec in VENUE_BOOKINGS:
        booking = db.get(VenueBooking, seed_id("venue-booking", spec.slug))
        venue = db.get(Venue, booking.venue_id)
        assert (booking.occupied_starts_at, booking.occupied_ends_at) == occupied_window(
            venue, booking.starts_at, booking.ends_at
        ), spec.slug


# --- TC-US13-02 the occupied window ---


def test_tc_us13_02_occupied_window_adds_setup_before_and_turnaround_after() -> None:
    """AC 2's example: 10:00-12:00 with 30 min setup and 45 min turnaround occupies 09:30-12:45."""
    venue = Venue(setup_minutes=30, turnaround_minutes=45)

    assert occupied_window(venue, at(10), at(12)) == (at(9, 30), at(12, 45))


def test_tc_us13_02_zero_buffers_occupy_the_plain_window() -> None:
    assert occupied_window(Venue(setup_minutes=0, turnaround_minutes=0), at(10), at(12)) == (at(10), at(12))


def test_tc_us13_02_the_factory_fills_the_occupied_window_from_the_venue(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))

    assert (booking.occupied_starts_at, booking.occupied_ends_at) == (at(9, 30), at(12, 45))


# --- TC-US13-03 the overlap guard covers the occupied window ---


def test_tc_us13_03_setup_overlapping_turnaround_by_one_second_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    """The plain windows don't touch (12:00 and 13:14:59), but 12:45's turnaround end and 12:44:59's
    setup start do overlap, by one second (AC 3)."""
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))

    constraint = refused_constraint(
        db, event=event, venue=venue, user=coordinator, starts_at=at(13, 14, 59), ends_at=at(14)
    )

    assert constraint == NO_OVERLAP


def test_tc_us13_03_setup_may_start_as_the_earlier_turnaround_ends(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    """Touching windows don't conflict: 12:45 turnaround end, 12:45 setup start (AC 3)."""
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))

    later = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(13, 15), ends_at=at(14))
    earlier = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(7, 15), ends_at=at(8, 45))

    assert later.occupied_starts_at == at(12, 45)
    assert earlier.occupied_ends_at == at(9, 30)


def test_tc_us13_03_a_plain_window_inside_anothers_setup_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))

    constraint = refused_constraint(db, event=event, venue=venue, user=coordinator, starts_at=at(9), ends_at=at(9, 45))

    assert constraint == NO_OVERLAP


@pytest.mark.parametrize("existing", [VenueBookingStatus.WITHDRAWN, VenueBookingStatus.REJECTED])
def test_tc_us13_03_withdrawn_and_rejected_bookings_occupy_nothing(
    db: Session, event: Event, venue: Venue, coordinator: User, existing: VenueBookingStatus
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12), status=existing)

    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(12, 30), ends_at=at(14))

    assert booking.status == VenueBookingStatus.REQUESTED


def test_tc_us13_03_another_venue_is_unaffected(db: Session, event: Event, venue: Venue, coordinator: User) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(12))

    elsewhere = make_venue_booking(
        db, event=event, venue=make_venue(db, name="Other Room"), user=coordinator, starts_at=at(12), ends_at=at(13)
    )

    assert elsewhere.status == VenueBookingStatus.REQUESTED


# --- TC-US13-04 the migration ---


def alembic_config(connection: Connection) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
def migration_connection(engine: Engine) -> Generator[Connection, None, None]:
    """DDL is transactional in Postgres, so migrating down and up here is rolled back afterwards and
    the rest of the suite keeps the schema at head."""
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


def insert_rows(connection: Connection, *, setup: int, turnaround: int, windows: list[tuple[datetime, datetime]]) -> list[uuid.UUID]:
    """A venue with these buffers, and one requested booking per window, as the schema before US13."""
    user_id, event_id, venue_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text("insert into users (id, email, role) values (:id, :email, 'coordinator')"),
        {"id": user_id, "email": f"{user_id.hex}@smu.edu.sg"},
    )
    connection.execute(text("insert into events (id, status) values (:id, 'approved')"), {"id": event_id})
    connection.execute(
        text(
            "insert into venues (id, name, location, capacity, opens_at, closes_at, setup_minutes, turnaround_minutes) "
            "values (:id, 'Migrated Room', 'Somewhere', 40, '07:00', '22:00', :setup, :turnaround)"
        ),
        {"id": venue_id, "setup": setup, "turnaround": turnaround},
    )
    ids = []
    for minutes, (starts_at, ends_at) in enumerate(windows):
        booking_id = uuid.uuid4()
        connection.execute(
            text(
                "insert into venue_bookings (id, event_id, venue_id, requested_by_user_id, starts_at, ends_at, "
                "expected_attendees, room_layout, created_at) "
                "values (:id, :event, :venue, :user, :starts, :ends, 10, 'theatre', :created)"
            ),
            {
                "id": booking_id,
                "event": event_id,
                "venue": venue_id,
                "user": user_id,
                "starts": starts_at,
                "ends": ends_at,
                "created": NOW + timedelta(minutes=minutes),
            },
        )
        ids.append(booking_id)
    return ids


def test_tc_us13_04_the_upgrade_backfills_occupied_windows_and_references(migration_connection: Connection) -> None:
    config = alembic_config(migration_connection)
    command.downgrade(config, PREVIOUS_REVISION)
    first, second = insert_rows(
        migration_connection, setup=30, turnaround=45, windows=[(at(10), at(12)), (at(15), at(16))]
    )

    command.upgrade(config, "head")

    rows = {
        row.id: row
        for row in migration_connection.execute(
            text("select id, occupied_starts_at, occupied_ends_at, reference from venue_bookings where id in (:a, :b)"),
            {"a": first, "b": second},
        )
    }
    assert (rows[first].occupied_starts_at, rows[first].occupied_ends_at) == (at(9, 30), at(12, 45))
    assert (rows[second].occupied_starts_at, rows[second].occupied_ends_at) == (at(14, 30), at(16, 45))
    # Numbered in the order the bookings were made, under the year they were made in.
    year = NOW.astimezone(SINGAPORE).year
    references = [rows[first].reference, rows[second].reference]
    assert all(re.fullmatch(rf"VB-{year}-\d{{6}}", reference) for reference in references)
    assert references == sorted(references)


def test_tc_us13_04_the_upgrade_refuses_bookings_that_buffers_would_make_overlap(
    migration_connection: Connection,
) -> None:
    """CR-01: bookings that become conflicting are identified, not removed. Back-to-back plain windows
    were fine before US13; with 30/45 buffers they overlap, so the migration stops and names them."""
    config = alembic_config(migration_connection)
    command.downgrade(config, PREVIOUS_REVISION)
    first, second = insert_rows(
        migration_connection, setup=30, turnaround=45, windows=[(at(10), at(12)), (at(12), at(13))]
    )

    with pytest.raises(RuntimeError) as raised:
        command.upgrade(config, "head")

    assert "overlap" in str(raised.value)
    assert str(first) in str(raised.value) and str(second) in str(raised.value)


def test_tc_us13_04_downgrade_restores_the_plain_window_guard(migration_connection: Connection) -> None:
    config = alembic_config(migration_connection)

    command.downgrade(config, PREVIOUS_REVISION)

    definition = migration_connection.scalar(
        text("select pg_get_constraintdef(oid) from pg_constraint where conname = :name"), {"name": NO_OVERLAP}
    )
    assert "tstzrange(starts_at, ends_at, '[)'::text)" in definition
    columns = {column["name"] for column in inspect(migration_connection).get_columns("venue_bookings")}
    assert not {"occupied_starts_at", "occupied_ends_at", "reference"} & columns
    assert migration_connection.scalar(text("select to_regclass('venue_booking_reference_seq')")) is None


# --- TC-US13-05 booking references ---


def test_tc_us13_05_each_booking_gets_a_reference_in_order(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    first = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(11))
    second = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(15), ends_at=at(16))
    db.refresh(first)
    db.refresh(second)

    # The year a booking is made in, in Singapore, as the database's clock has it.
    year = db.scalar(text("select extract(year from now() at time zone 'Asia/Singapore')::int"))
    for booking in (first, second):
        assert re.fullmatch(rf"VB-{year}-\d{{6}}", booking.reference), booking.reference
    assert int(first.reference[-6:]) < int(second.reference[-6:])


def test_tc_us13_05_two_bookings_cannot_share_a_reference(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    first = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(10), ends_at=at(11))
    db.refresh(first)

    constraint = refused_constraint(
        db, event=event, venue=venue, user=coordinator, starts_at=at(15), ends_at=at(16), reference=first.reference
    )

    assert constraint == "venue_bookings_reference_key"


def test_tc_us13_05_seeded_bookings_have_references(db: Session) -> None:
    seed(db, now=NOW)

    references = db.scalars(
        select(VenueBooking.reference).where(VenueBooking.id.in_([seed_id("venue-booking", s.slug) for s in VENUE_BOOKINGS]))
    ).all()
    assert len(references) == len(VENUE_BOOKINGS)
    assert all(reference.startswith("VB-") for reference in references)
