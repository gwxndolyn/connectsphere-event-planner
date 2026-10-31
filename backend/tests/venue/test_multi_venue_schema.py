"""US24 multiple venues for one event, PR 1 (SCRUM-127, story SCRUM-92): each booking has a purpose
and may be its event's primary venue, at most one live primary per event; the migration backfills both
and the seed gives events their venues. The endpoints come in PR 2. See docs/testing/US24-multi-venue.md."""

import uuid
from collections.abc import Generator
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import DeliveryMode, Event, EventStatus
from app.seed import EQUIPMENT_EVENT, EVENTS, MULTI_VENUE_EVENT, EventSpec, VENUE_BOOKINGS, VENUES, seed, seed_id, seeded_booking_count
from app.user.models import User, UserRole
from app.venue.models import LIVE_BOOKING_STATUSES, Venue, VenueBooking, VenueBookingStatus
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

REVISION = "20261103_1200_us24_multi_venue"
PREVIOUS_REVISION = "20261102_1200_us5_check_outcome"  # US24 follows US5 PR 2 since #94 merged
ONE_PRIMARY = "venue_bookings_one_primary_per_event"
PURPOSE_CHECK = "venue_bookings_purpose_valid"
PREPARATION_CHECK = "venue_bookings_preparation_status_known"
SINGAPORE = ZoneInfo("Asia/Singapore")
DAY = (NOW + timedelta(days=7)).date()


def at(hour: int) -> datetime:
    return datetime.combine(DAY, time(hour), SINGAPORE)


@pytest.fixture
def event(db: Session) -> Event:
    # DECISION-PENDING: D24 — tests put the event straight into approved.
    return make_event(db, status=EventStatus.APPROVED)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db, setup_minutes=0, turnaround_minutes=0)


def refused_constraint(db: Session, **booking: object) -> str:
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_venue_booking(db, **booking)
    return raised.value.orig.diag.constraint_name


# --- TC-US24-01 schema and the migration's backfill ---


def test_tc_us24_01_bookings_have_a_purpose_a_primary_flag_and_a_preparation_status(engine: Engine) -> None:
    columns = {column["name"]: column for column in inspect(engine).get_columns("venue_bookings")}

    assert columns["purpose"]["nullable"] is False
    assert columns["is_primary"]["nullable"] is False
    assert "false" in str(columns["is_primary"]["default"])
    # D73 (CS3-49): preparation is tracked per venue, not_started until Venue staff move it on.
    assert columns["preparation_status"]["nullable"] is False
    assert "not_started" in str(columns["preparation_status"]["default"])
    checks = {constraint["name"] for constraint in inspect(engine).get_check_constraints("venue_bookings")}
    assert {PURPOSE_CHECK, PREPARATION_CHECK} <= checks
    indexes = {index["name"]: index for index in inspect(engine).get_indexes("venue_bookings")}
    assert indexes[ONE_PRIMARY]["unique"] is True
    assert indexes[ONE_PRIMARY]["column_names"] == ["event_id"]


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


def insert_old_rows(connection: Connection, bookings: list[tuple[str, str, int]]) -> dict[str, uuid.UUID]:
    """Bookings as the schema before US24 holds them: (name, event, minutes after NOW it was made),
    each status taken from the name's first word. Returns the booking ids by name."""
    user_id, venue_id = uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text("insert into users (id, email, roles) values (:id, :email, '{coordinator}')"),
        {"id": user_id, "email": f"{user_id.hex}@smu.edu.sg"},
    )
    connection.execute(
        text(
            "insert into venues (id, name, location, capacity, opens_at, closes_at, setup_minutes, turnaround_minutes) "
            "values (:id, 'Migrated Room', 'Somewhere', 40, '07:00', '22:00', 0, 0)"
        ),
        {"id": venue_id},
    )
    events: dict[str, uuid.UUID] = {}
    ids: dict[str, uuid.UUID] = {}
    for hour, (name, event, minutes) in enumerate(bookings, start=8):
        if event not in events:
            events[event] = uuid.uuid4()
            connection.execute(text("insert into events (id, status) values (:id, 'approved')"), {"id": events[event]})
        status = name.split()[0]
        made = NOW + timedelta(minutes=minutes)
        ids[name] = uuid.uuid4()
        connection.execute(
            text(
                "insert into venue_bookings (id, event_id, venue_id, requested_by_user_id, starts_at, ends_at, "
                "occupied_starts_at, occupied_ends_at, expected_attendees, room_layout, status, created_at, "
                "withdrawn_at, decided_at) "
                "values (:id, :event, :venue, :user, :starts, :ends, :starts, :ends, 10, 'theatre', :status, :made, "
                ":withdrawn, :decided)"
            ),
            {
                "id": ids[name],
                "event": events[event],
                "venue": venue_id,
                "user": user_id,
                "starts": at(hour),
                "ends": at(hour) + timedelta(minutes=30),
                "status": status,
                "made": made,
                "withdrawn": made if status == "withdrawn" else None,
                "decided": made if status in ("approved", "rejected") else None,
            },
        )
    return ids


def test_tc_us24_01_the_upgrade_names_existing_bookings_and_marks_each_events_first_live_one_primary(
    migration_connection: Connection,
) -> None:
    config = alembic_config(migration_connection)
    command.downgrade(config, PREVIOUS_REVISION)
    ids = insert_old_rows(
        migration_connection,
        [
            # Event A: the earliest booking was withdrawn, so the first live one (requested) is primary.
            ("withdrawn first", "A", 0),
            ("requested second", "A", 1),
            ("approved third", "A", 2),
            # Event B: nothing live, so no primary.
            ("rejected only", "B", 0),
            # Event C: one approved booking.
            ("approved alone", "C", 0),
        ],
    )

    command.upgrade(config, "head")

    rows = {
        row.id: row
        for row in migration_connection.execute(
            text("select id, purpose, is_primary, preparation_status from venue_bookings where id = any(:ids)"),
            {"ids": list(ids.values())},
        )
    }
    assert {row.purpose for row in rows.values()} == {"Main venue"}
    assert {row.preparation_status for row in rows.values()} == {"not_started"}
    primary = {name for name, booking_id in ids.items() if rows[booking_id].is_primary}
    assert primary == {"requested second", "approved alone"}


def test_tc_us24_01_downgrade_removes_purpose_primary_preparation_and_the_index(migration_connection: Connection) -> None:
    config = alembic_config(migration_connection)

    command.downgrade(config, PREVIOUS_REVISION)

    columns = {column["name"] for column in inspect(migration_connection).get_columns("venue_bookings")}
    assert not {"purpose", "is_primary", "preparation_status"} & columns
    assert migration_connection.scalar(text("select to_regclass(:name)"), {"name": ONE_PRIMARY}) is None

    command.upgrade(config, "head")
    columns = {column["name"] for column in inspect(migration_connection).get_columns("venue_bookings")}
    assert {"purpose", "is_primary", "preparation_status"} <= columns


def test_tc_us24_01_downgrade_keeps_bookings_whose_us24_values_are_the_defaults(migration_connection: Connection) -> None:
    """Only the primary flag is lost, and the upgrade works it out again (#96 review)."""
    config = alembic_config(migration_connection)
    ids = insert_old_rows(migration_connection, [("approved main", "A", 0), ("requested other", "A", 1)])

    command.downgrade(config, PREVIOUS_REVISION)
    command.upgrade(config, "head")

    rows = migration_connection.execute(
        text("select purpose, preparation_status, is_primary from venue_bookings where id = any(:ids) order by created_at"),
        {"ids": list(ids.values())},
    ).all()
    assert [tuple(row) for row in rows] == [("Main venue", "not_started", True), ("Main venue", "not_started", False)]


@pytest.mark.parametrize(
    ("column", "value"),
    [("purpose", "Breakout A"), ("preparation_status", "in_progress"), ("preparation_status", "ready")],
)
def test_tc_us24_01_downgrade_refuses_to_discard_a_purpose_or_preparation_progress(
    migration_connection: Connection, column: str, value: str
) -> None:
    """#96 review: like US26's and US5's, the downgrade won't drop what someone entered."""
    config = alembic_config(migration_connection)
    ids = insert_old_rows(migration_connection, [("approved main", "A", 0)])
    migration_connection.execute(
        text(f"update venue_bookings set {column} = :value where id = :id"), {"value": value, "id": ids["approved main"]}
    )

    with pytest.raises(RuntimeError) as raised:
        command.downgrade(config, PREVIOUS_REVISION)

    assert "Refusing lossy downgrade" in str(raised.value)
    columns = {column["name"] for column in inspect(migration_connection).get_columns("venue_bookings")}
    assert {"purpose", "is_primary", "preparation_status"} <= columns


# --- TC-US24-02 one live primary per event ---


def test_tc_us24_02_a_second_live_primary_for_the_same_event_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(9), is_primary=True)

    for status in LIVE_BOOKING_STATUSES:
        assert (
            refused_constraint(
                db, event=event, venue=venue, user=coordinator, starts_at=at(12), status=status, is_primary=True
            )
            == ONE_PRIMARY
        )


def test_tc_us24_02_a_withdrawn_or_rejected_primary_does_not_block_a_new_one(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=at(9), status=VenueBookingStatus.WITHDRAWN, is_primary=True
    )
    make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=at(11), status=VenueBookingStatus.REJECTED, is_primary=True
    )

    live = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(13), is_primary=True)

    assert live.is_primary is True


def test_tc_us24_02_each_event_has_its_own_primary_and_others_are_not_primary(
    db: Session, event: Event, venue: Venue, coordinator: User
) -> None:
    other_event = make_event(db, status=EventStatus.APPROVED)
    make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(9), is_primary=True)
    make_venue_booking(db, event=other_event, venue=venue, user=coordinator, starts_at=at(12), is_primary=True)

    # Any number of non-primary bookings sit beside the primary.
    breakout = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(15))
    another = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(18))

    assert (breakout.is_primary, another.is_primary) == (False, False)


# --- TC-US24-03 purpose ---


@pytest.mark.parametrize("purpose", ["", "   ", " Main hall", "Main hall ", "x" * 101])
def test_tc_us24_03_a_blank_untrimmed_or_overlong_purpose_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User, purpose: str
) -> None:
    assert refused_constraint(db, event=event, venue=venue, user=coordinator, purpose=purpose) == PURPOSE_CHECK


@pytest.mark.parametrize("purpose", ["Breakout A", "x" * 100, "B"])
def test_tc_us24_03_a_purpose_of_1_to_100_characters_is_accepted(
    db: Session, event: Event, venue: Venue, coordinator: User, purpose: str
) -> None:
    booking = make_venue_booking(db, event=event, venue=venue, user=coordinator, purpose=purpose)

    assert db.scalar(select(VenueBooking.purpose).where(VenueBooking.id == booking.id)) == purpose


@pytest.mark.parametrize("preparation_status", ["", "done", "Ready", "in progress", "cancelled"])
def test_tc_us24_03_an_unknown_preparation_status_is_refused(
    db: Session, event: Event, venue: Venue, coordinator: User, preparation_status: str
) -> None:
    assert (
        refused_constraint(db, event=event, venue=venue, user=coordinator, preparation_status=preparation_status)
        == PREPARATION_CHECK
    )


@pytest.mark.parametrize("preparation_status", ["not_started", "in_progress", "ready"])
def test_tc_us24_03_each_preparation_status_is_accepted_and_a_new_booking_has_not_started(
    db: Session, event: Event, venue: Venue, coordinator: User, preparation_status: str
) -> None:
    fresh = make_venue_booking(db, event=event, venue=venue, user=coordinator, starts_at=at(9))
    set_one = make_venue_booking(
        db, event=event, venue=venue, user=coordinator, starts_at=at(12), preparation_status=preparation_status
    )

    stored = dict(
        db.execute(
            select(VenueBooking.id, VenueBooking.preparation_status).where(VenueBooking.id.in_([fresh.id, set_one.id]))
        ).all()
    )
    assert stored == {fresh.id: "not_started", set_one.id: preparation_status}


# --- TC-US24-04 the seed ---


def live_bookings(db: Session, event_id: uuid.UUID) -> list[VenueBooking]:
    return db.scalars(
        select(VenueBooking).where(VenueBooking.event_id == event_id, VenueBooking.status.in_(LIVE_BOOKING_STATUSES))
    ).all()


def test_tc_us24_04_each_in_person_seeded_event_names_its_venue_and_none_is_assumed() -> None:
    """#96 review: no default venue, so a new seeded event gets a booking only when it names one."""
    assert EventSpec.__dataclass_fields__["venue_slug"].default is None
    assert {spec.slug: spec.venue_slug for spec in [*EVENTS, EQUIPMENT_EVENT]} == {
        "tech-talk-agile": "scis-seminar-2-1",
        "design-sprint-bootcamp": "connexion-studio-3-2",
        "supabase-live-coding": None,  # online
        "startup-pitch-night": "mochtar-riady-auditorium",
        "career-fair-prep": "lks-library-seminar-3-4",
        "wellness-week-yoga": "campus-green-lawn-c",
        "orientation-debrief": None,  # no seeded venue at the School of Accountancy
        "equipment-request-demo": "scis-seminar-2-1",
    }


def test_tc_us24_04_each_seeded_in_person_event_with_a_seeded_venue_has_an_approved_primary_booking(
    db: Session,
) -> None:
    seed(db, now=NOW)
    seed(db, now=NOW)  # idempotent

    capacities = {seed_id("venue", spec.slug): spec.capacity for spec in VENUES}
    with_venue = [spec for spec in [*EVENTS, EQUIPMENT_EVENT] if spec.venue_slug]
    assert len(with_venue) >= 5
    for spec in with_venue:
        event = db.get(Event, seed_id("event", spec.slug))
        assert event.delivery_mode == DeliveryMode.IN_PERSON, spec.slug
        [booking] = live_bookings(db, event.id)
        assert booking.venue_id == seed_id("venue", spec.venue_slug), spec.slug
        assert booking.status == VenueBookingStatus.APPROVED
        assert booking.is_primary is True
        assert booking.purpose == "Main venue"
        # The event's own schedule (D65), and an allocation the venue holds (US24 AC 3).
        assert (booking.starts_at, booking.ends_at) == (event.start_at, event.end_at), spec.slug
        assert booking.expected_attendees <= capacities[booking.venue_id]
        assert booking.decided_by_user_id == seed_id("user", "venue-staff")
        assert booking.preparation_status == "not_started"


def test_tc_us24_04_the_seed_summary_counts_every_booking_it_seeds(db: Session) -> None:
    seed(db, now=NOW)
    seed(db, now=NOW)

    # The test database starts empty, so every booking here is one the seed owns.
    assert db.scalar(select(func.count()).select_from(VenueBooking)) == seeded_booking_count() == 11


def test_tc_us24_04_online_events_and_ones_without_a_seeded_venue_have_none(db: Session) -> None:
    seed(db, now=NOW)

    for spec in EVENTS:
        if spec.venue_slug is None:
            assert live_bookings(db, seed_id("event", spec.slug)) == [], spec.slug
    assert any(spec.delivery_mode == DeliveryMode.ONLINE and spec.venue_slug is None for spec in EVENTS)


def test_tc_us24_04_the_us2_slot_bookings_are_their_events_primary(db: Session) -> None:
    seed(db, now=NOW)

    for spec in VENUE_BOOKINGS:
        booking = db.get(VenueBooking, seed_id("venue-booking", spec.slug))
        assert (booking.is_primary, booking.purpose) == (True, "Main venue"), spec.slug


def test_tc_us24_04_the_multi_venue_demo_event_has_approved_requested_and_rejected_venues(db: Session) -> None:
    seed(db, now=NOW)

    event = db.get(Event, seed_id("event", MULTI_VENUE_EVENT.slug))
    assert event.name == "Multi-Venue Conference Demo"
    assert event.status == EventStatus.APPROVED
    # The dev coordinator can book it (D20); the seeded organiser owns it.
    assert event.coordinator_id == seed_id("user", "event-coordinator")
    assert event.created_by_user_id == seed_id("user", "event-organiser")
    bookings = db.scalars(select(VenueBooking).where(VenueBooking.event_id == event.id)).all()
    by_purpose = {booking.purpose: booking for booking in bookings}
    assert {purpose: (b.status, b.is_primary) for purpose, b in by_purpose.items()} == {
        "Main hall": (VenueBookingStatus.APPROVED, True),
        "Breakout A": (VenueBookingStatus.REQUESTED, False),
        "Breakout B": (VenueBookingStatus.REJECTED, False),
    }
    assert by_purpose["Breakout B"].rejection_reason
    # D73 (CS3-49): Venue staff are preparing the approved main hall; nothing else has started.
    assert {purpose: b.preparation_status for purpose, b in by_purpose.items()} == {
        "Main hall": "in_progress",
        "Breakout A": "not_started",
        "Breakout B": "not_started",
    }
    # Each window falls on the event's preferred day, within its preferred times (D65).
    for booking in bookings:
        local_start = booking.starts_at.astimezone(SINGAPORE)
        local_end = booking.ends_at.astimezone(SINGAPORE)
        assert local_start.date() in event.preferred_dates
        assert event.preferred_start_time <= local_start.time() and local_end.time() <= event.preferred_end_time
    assert len({booking.venue_id for booking in bookings}) == 3


def test_tc_us24_04_reseeding_puts_the_primary_back_on_the_main_hall(db: Session) -> None:
    seed(db, now=NOW)
    event_id = seed_id("event", MULTI_VENUE_EVENT.slug)
    by_purpose = {b.purpose: b for b in db.scalars(select(VenueBooking).where(VenueBooking.event_id == event_id))}
    # As if the coordinator had made Breakout A primary in the app.
    by_purpose["Main hall"].is_primary = False
    db.flush()
    by_purpose["Breakout A"].is_primary = True
    db.flush()

    seed(db, now=NOW)

    db.expire_all()
    primary = db.scalars(
        select(VenueBooking.purpose).where(VenueBooking.event_id == event_id, VenueBooking.is_primary.is_(True))
    ).all()
    assert primary == ["Main hall"]
