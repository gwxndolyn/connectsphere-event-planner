"""US5 equipment availability, PR 2 (SCRUM-125, story SCRUM-9): Tech Support checks whether a request
line's type and quantity are available for its event's own times, and the line records the latest outcome
(D64). The stock and reservations tables are PR 1's (test_equipment_stock_schema.py); see
docs/testing/US5-equipment-availability.md."""

import uuid
from datetime import datetime, timedelta

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentReservation, EquipmentType
from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

# The line's event: 10:00 to 13:00, three days after NOW.
STARTS = NOW.replace(hour=10) + timedelta(days=3)
ENDS = STARTS + timedelta(hours=3)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


QUEUE_URL = "/api/v1/equipment-lines"


def line_url(line_id: uuid.UUID) -> str:
    return f"/api/v1/equipment-lines/{line_id}"


def check_url(line_id: uuid.UUID) -> str:
    return f"/api/v1/equipment-lines/{line_id}/availability-check"


def make_type(
    db: Session, total: int = 10, out_of_service: int = 0, location: str | None = "AV store, Level B1"
) -> EquipmentType:
    equipment_type = EquipmentType(
        name=f"Test type {uuid.uuid4().hex[:8]}",
        total_quantity=total,
        out_of_service_quantity=out_of_service,
        storage_location=location,
    )
    db.add(equipment_type)
    db.flush()
    return equipment_type


def make_line(
    db: Session, event: Event, equipment_type: EquipmentType, quantity: int, requested_by: User | None = None
) -> EquipmentRequestLine:
    line = EquipmentRequestLine(
        event_id=event.id,
        equipment_type_id=equipment_type.id,
        quantity=quantity,
        requested_by_user_id=(requested_by.id if requested_by else event.coordinator_id),
    )
    db.add(line)
    db.flush()
    return line


def other_event(db: Session, start_at: datetime, end_at: datetime) -> Event:
    return make_event(db, name="Other event", status=EventStatus.CONFIRMED, start_at=start_at, end_at=end_at)


def reserve(
    db: Session,
    event: Event,
    equipment_type: EquipmentType,
    quantity: int,
    line: EquipmentRequestLine | None = None,
) -> EquipmentReservation:
    """Units reserved for `event`. A reservation fulfils one line (US27, SCRUM-130): an approved line
    made for it, or `line`."""
    if line is None:
        reviewer = make_user(db, UserRole.TECH_SUPPORT)
        line = make_line(db, event, equipment_type, quantity, requested_by=make_user(db, UserRole.COORDINATOR))
        line.status, line.reviewed_by_user_id, line.reviewed_at = EquipmentLineStatus.APPROVED, reviewer.id, NOW
        db.flush()
    reservation = EquipmentReservation(
        request_line_id=line.id,
        event_id=event.id,
        equipment_type_id=equipment_type.id,
        quantity=quantity,
        reserved_by_user_id=make_user(db, UserRole.TECH_SUPPORT).id,
    )
    db.add(reservation)
    db.flush()
    return reservation


@pytest.fixture
def tech(db: Session) -> User:
    return make_user(db, UserRole.TECH_SUPPORT)


@pytest.fixture
def event(db: Session) -> Event:
    coordinator = make_user(db, UserRole.COORDINATOR)
    return make_event(
        db, name="Data Science Summit", status=EventStatus.CONFIRMED, start_at=STARTS, end_at=ENDS,
        coordinator_id=coordinator.id,
    )


async def check(client: AsyncClient, user: User, line: EquipmentRequestLine) -> dict:
    response = await client.post(check_url(line.id), headers=auth(user))
    assert response.status_code == 200, response.text
    return response.json()


async def test_tc_us5_04_available_is_stock_less_out_of_service_and_other_reservations(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    projector = make_type(db, total=10, out_of_service=2, location="AV store, Level B1")
    reserve(db, other_event(db, STARTS + timedelta(hours=1), ENDS + timedelta(hours=1)), projector, 3)
    line = make_line(db, event, projector, quantity=4)

    body = await check(client, tech, line)

    assert body["line_id"] == str(line.id)
    assert body["equipment_type"] == {
        "id": str(projector.id),
        "name": projector.name,
        "storage_location": "AV store, Level B1",
    }
    assert datetime.fromisoformat(body["window"]["starts_at"]) == STARTS
    assert datetime.fromisoformat(body["window"]["ends_at"]) == ENDS
    assert {key: body[key] for key in ("requested", "total", "out_of_service", "reserved_elsewhere", "available")} == {
        "requested": 4,
        "total": 10,
        "out_of_service": 2,
        "reserved_elsewhere": 3,
        "available": 5,
    }
    assert (body["sufficient"], body["shortfall"]) == (True, 0)


async def test_tc_us5_05_only_overlapping_other_events_reservations_count(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    projector = make_type(db, total=20)
    reserve(db, other_event(db, STARTS - timedelta(hours=1), STARTS + timedelta(hours=1)), projector, 3)  # overlaps
    reserve(db, other_event(db, ENDS, ENDS + timedelta(hours=2)), projector, 4)  # back-to-back after
    reserve(db, other_event(db, STARTS - timedelta(hours=2), STARTS), projector, 5)  # back-to-back before
    reserve(db, other_event(db, STARTS + timedelta(days=1), ENDS + timedelta(days=1)), projector, 6)  # another day
    reserve(db, other_event(db, STARTS, ENDS), make_type(db), 7)  # another type
    line = make_line(db, event, projector, quantity=1)
    # The line's own event: the line itself reserved (D41 allows no second live line of the type there).
    reserve(db, event, projector, 2, line=line)

    body = await check(client, tech, line)

    assert body["reserved_elsewhere"] == 3
    assert body["available"] == 17


async def test_tc_us5_06_venue_setup_and_turnaround_are_not_added(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    # The earlier event, at a venue with a 30-minute turnaround, ends 10 minutes before this one starts
    # at another venue, so its occupied window runs 20 minutes into this event. Equipment goes by the
    # events' own times (AC 6), so its reservation doesn't count. (At one venue the two couldn't both be
    # booked: venue_bookings_no_overlap refuses the turnaround clash.)
    earlier = other_event(db, STARTS - timedelta(hours=2), STARTS - timedelta(minutes=10))
    booked = []
    for booked_event, venue_name in ((earlier, "Hall A"), (event, "Hall B")):
        booked.append(
            make_venue_booking(
                db, event=booked_event, venue=make_venue(db, name=venue_name, setup_minutes=30, turnaround_minutes=30),
                user=make_user(db, UserRole.COORDINATOR), starts_at=booked_event.start_at, ends_at=booked_event.end_at,
            )
        )
    assert booked[0].occupied_ends_at > booked[1].starts_at
    projector = make_type(db, total=5)
    reserve(db, earlier, projector, 5)
    line = make_line(db, event, projector, quantity=5)

    body = await check(client, tech, line)

    assert (body["reserved_elsewhere"], body["available"], body["sufficient"]) == (0, 5, True)
    assert datetime.fromisoformat(body["window"]["starts_at"]) == STARTS
    assert datetime.fromisoformat(body["window"]["ends_at"]) == ENDS


async def test_tc_us5_07_a_short_line_shows_the_shortfall(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    speakers = make_type(db, total=3, out_of_service=1)
    line = make_line(db, event, speakers, quantity=5)

    body = await check(client, tech, line)

    assert (body["available"], body["sufficient"], body["shortfall"]) == (2, False, 3)


async def test_tc_us5_07_available_is_never_negative(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    # Stock can drop below what's already reserved (units go out of service after a reservation).
    webcams = make_type(db, total=4, out_of_service=2)
    reserve(db, other_event(db, STARTS, ENDS), webcams, 3)
    line = make_line(db, event, webcams, quantity=2)

    body = await check(client, tech, line)

    assert (body["reserved_elsewhere"], body["available"], body["sufficient"], body["shortfall"]) == (3, 0, False, 2)


async def test_tc_us5_08_the_line_records_the_latest_outcome(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    # D64: the outcome is stored on the line (latest only); the check never reserves or reviews (AC 5).
    projector = make_type(db, total=10)
    line = make_line(db, event, projector, quantity=4)

    first = await check(client, tech, line)
    second = await check(client, tech, line)

    assert first == second
    db.refresh(line)
    assert (line.availability_sufficient, line.availability_shortfall) == (True, 0)
    assert (line.availability_checked_by_user_id, line.availability_checked_at) == (tech.id, NOW)
    assert (line.status, line.quantity, line.reviewed_by_user_id, line.review_note) == (
        EquipmentLineStatus.PENDING, 4, None, None
    )
    assert db.scalar(select(func.count()).select_from(EquipmentReservation)) == 0

    # The queue shows each line's last check.
    queue = await client.get(QUEUE_URL, headers=auth(tech), params={"status": "pending"})
    [listed] = [item for item in queue.json()["lines"] if item["id"] == str(line.id)]
    assert listed["availability_check"]["sufficient"] is True
    assert listed["availability_check"]["shortfall"] == 0
    assert listed["availability_check"]["checked_by_user_id"] == str(tech.id)
    assert datetime.fromisoformat(listed["availability_check"]["checked_at"]) == NOW


async def test_tc_us5_08_a_newer_check_replaces_the_last(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    speakers = make_type(db, total=6)
    line = make_line(db, event, speakers, quantity=4)
    await check(client, tech, line)

    reserve(db, other_event(db, STARTS, ENDS), speakers, 5)
    await check(client, tech, line)

    db.refresh(line)
    assert (line.availability_sufficient, line.availability_shortfall) == (False, 3)


async def test_tc_us5_08_an_unchecked_line_has_no_outcome(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    line = make_line(db, event, make_type(db), quantity=1)

    queue = await client.get(QUEUE_URL, headers=auth(tech), params={"status": "pending"})

    [listed] = [item for item in queue.json()["lines"] if item["id"] == str(line.id)]
    assert listed["availability_check"] is None


async def test_tc_us5_09_a_type_without_a_location_is_still_checked(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    unlocated = make_type(db, total=6, out_of_service=1, location=None)
    located = make_type(db, total=6, out_of_service=1, location="IT service desk, Level 2")

    without = await check(client, tech, make_line(db, event, unlocated, quantity=3))
    with_location = await check(client, tech, make_line(db, event, located, quantity=3))

    assert without["equipment_type"]["storage_location"] is None
    # Location is for reference only: it never changes the result.
    keys = ("requested", "total", "out_of_service", "reserved_elsewhere", "available", "sufficient", "shortfall")
    assert {key: without[key] for key in keys} == {key: with_location[key] for key in keys}


@pytest.mark.parametrize("role", [role for role in UserRole if role != UserRole.TECH_SUPPORT])
async def test_tc_us5_10_only_tech_support_checks(
    client: AsyncClient, db: Session, event: Event, role: UserRole
) -> None:
    line = make_line(db, event, make_type(db), quantity=1)

    response = await client.post(check_url(line.id), headers=auth(make_user(db, role)))

    assert response.status_code == 403
    assert response.json() == {"code": "FORBIDDEN"}
    db.refresh(line)
    assert line.availability_checked_at is None


async def test_tc_us5_10_the_check_needs_an_identity(client: AsyncClient, db: Session, event: Event) -> None:
    line = make_line(db, event, make_type(db), quantity=1)

    response = await client.post(check_url(line.id))

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_tc_us5_10_an_unknown_line_is_404(client: AsyncClient, tech: User) -> None:
    response = await client.post(check_url(uuid.uuid4()), headers=auth(tech))

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND"}


@pytest.mark.parametrize(
    ("change", "cleared"),
    [({"quantity": 6}, True), ({"equipment_type": True}, True), ({"notes": "Spare bulbs too"}, False)],
    ids=["quantity", "type", "notes only"],
)
async def test_tc_us5_13_editing_the_quantity_or_type_clears_the_check(
    client: AsyncClient, db: Session, tech: User, event: Event, change: dict, cleared: bool
) -> None:
    # A check is for one type and quantity; after either changes it no longer applies (30 Oct).
    line = make_line(db, event, make_type(db), quantity=4)
    await check(client, tech, line)
    body = {"equipment_type_id": str(make_type(db).id)} if "equipment_type" in change else change
    coordinator = db.get(User, event.coordinator_id)

    response = await client.patch(line_url(line.id), headers=auth(coordinator), json=body)

    assert response.status_code == 200, response.text
    assert (response.json()["availability_check"] is None) is cleared
    db.refresh(line)
    assert (line.availability_checked_at is None) is cleared
    assert (line.availability_sufficient is None) is cleared


@pytest.mark.parametrize(
    "fields",
    [
        {"availability_checked_at": NOW},
        {"availability_checked_at": NOW, "availability_sufficient": True, "availability_shortfall": 0},
        {"availability_sufficient": True, "availability_shortfall": 2, "with_checker": True},
        {"availability_sufficient": False, "availability_shortfall": 0, "with_checker": True},
        # A NULL makes a CHECK pass unless it's ruled out explicitly (PR #94 review).
        {"with_checker": True},
        {"availability_sufficient": True, "with_checker": True},
        {"availability_shortfall": 2, "with_checker": True},
    ],
    ids=[
        "time only",
        "no checker",
        "sufficient but short",
        "short by nothing",
        "checker but no outcome",
        "sufficient without a shortfall",
        "shortfall without sufficient",
    ],
)
def test_tc_us5_14_a_recorded_check_is_whole_and_consistent(db: Session, event: Event, fields: dict) -> None:
    line = make_line(db, event, make_type(db), quantity=1)
    if fields.pop("with_checker", False):
        fields |= {"availability_checked_at": NOW, "availability_checked_by_user_id": make_user(db, UserRole.TECH_SUPPORT).id}

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            for key, value in fields.items():
                setattr(line, key, value)
            db.flush()

    assert raised.value.orig.diag.constraint_name == "equipment_request_lines_availability_check_consistent"


def test_tc_us5_14_one_head_with_the_check_outcome_columns(db: Session) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert "20261102_1200_us5_check_outcome" in {revision.revision for revision in script.walk_revisions()}
