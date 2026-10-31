"""US27 equipment reservations, PR 2 (SCRUM-131, story SCRUM-95): Tech Support reserves an approved line's
full quantity when it's available for the event's own times, and releases it. The line link is PR 1's
(test_equipment_reservation_schema.py); see docs/testing/US27-equipment-reservations.md."""

import threading
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

import app.equipment.service as equipment_service_module
from app.core.exceptions import DomainError
from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentReservation, EquipmentType
from app.equipment.service import equipment_service
from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from tests.factories import NOW, make_event, make_user, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

# The line's event: 10:00 to 13:00, three days after NOW.
STARTS = NOW.replace(hour=10) + timedelta(days=3)
ENDS = STARTS + timedelta(hours=3)
QUEUE_URL = "/api/v1/equipment-lines"


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def reservation_url(line_id: uuid.UUID) -> str:
    return f"/api/v1/equipment-lines/{line_id}/reservation"


def check_url(line_id: uuid.UUID) -> str:
    return f"/api/v1/equipment-lines/{line_id}/availability-check"


def make_type(db: Session, total: int = 10, out_of_service: int = 0) -> EquipmentType:
    equipment_type = EquipmentType(
        name=f"Test type {uuid.uuid4().hex[:8]}", total_quantity=total, out_of_service_quantity=out_of_service
    )
    db.add(equipment_type)
    db.flush()
    return equipment_type


def make_line(
    db: Session,
    event: Event,
    equipment_type: EquipmentType,
    quantity: int,
    status: EquipmentLineStatus = EquipmentLineStatus.APPROVED,
) -> EquipmentRequestLine:
    reviewer = make_user(db, UserRole.TECH_SUPPORT)
    line = EquipmentRequestLine(
        event_id=event.id,
        equipment_type_id=equipment_type.id,
        quantity=quantity,
        requested_by_user_id=event.coordinator_id or make_user(db, UserRole.COORDINATOR).id,
        status=status,
    )
    if status != EquipmentLineStatus.PENDING:
        line.reviewed_by_user_id, line.reviewed_at = reviewer.id, NOW - timedelta(hours=1)
    db.add(line)
    db.flush()
    return line


def make_event_at(db: Session, start_at: datetime, end_at: datetime, **fields) -> Event:
    coordinator = make_user(db, UserRole.COORDINATOR)
    fields = {"status": EventStatus.CONFIRMED, "coordinator_id": coordinator.id} | fields
    return make_event(db, name="Event", start_at=start_at, end_at=end_at, **fields)


def reserved(db: Session, event: Event, equipment_type: EquipmentType, quantity: int) -> EquipmentReservation:
    """Units already reserved for `event`, through an approved line of its own."""
    line = make_line(db, event, equipment_type, quantity)
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


def reservation_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(EquipmentReservation))


@pytest.fixture
def tech(db: Session) -> User:
    return make_user(db, UserRole.TECH_SUPPORT)


@pytest.fixture
def event(db: Session) -> Event:
    return make_event_at(db, STARTS, ENDS)


async def test_tc_us27_05_an_approved_line_is_reserved_in_full(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    projector = make_type(db, total=10)
    line = make_line(db, event, projector, quantity=4)

    response = await client.post(reservation_url(line.id), headers=auth(tech))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == str(line.id)
    assert body["reservation"]["quantity"] == 4
    assert body["reservation"]["reserved_by_user_id"] == str(tech.id)
    assert body["reservation"]["reserved_at"]
    assert body["reservation"]["released_because_event_cancelled"] is False
    [reservation] = db.scalars(select(EquipmentReservation).where(EquipmentReservation.request_line_id == line.id))
    assert (reservation.event_id, reservation.equipment_type_id, reservation.quantity) == (event.id, projector.id, 4)
    assert reservation.reserved_by_user_id == tech.id


async def test_tc_us27_06_a_quantity_cant_be_sent(client: AsyncClient, db: Session, tech: User, event: Event) -> None:
    line = make_line(db, event, make_type(db), quantity=4)

    response = await client.post(reservation_url(line.id), headers=auth(tech), json={"quantity": 2})

    assert response.status_code == 422
    assert reservation_count(db) == 0


async def test_tc_us27_07_more_than_is_available_is_refused(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    speakers = make_type(db, total=6, out_of_service=1)
    reserved(db, make_event_at(db, STARTS + timedelta(hours=1), ENDS + timedelta(hours=1)), speakers, 3)
    line = make_line(db, event, speakers, quantity=4)
    before = reservation_count(db)

    response = await client.post(reservation_url(line.id), headers=auth(tech))

    assert response.status_code == 409
    assert response.json() == {"code": "INSUFFICIENT_EQUIPMENT", "available": 2, "requested": 4, "shortfall": 2}
    assert reservation_count(db) == before


async def test_tc_us27_08_the_boundaries_fit(client: AsyncClient, db: Session, tech: User, event: Event) -> None:
    # Exactly enough: 5 owned, none elsewhere, a line for 5.
    exact = make_type(db, total=5)
    assert (await client.post(reservation_url(make_line(db, event, exact, 5).id), headers=auth(tech))).status_code == 201

    # Back-to-back: another event ending as this one starts holds all 5; it doesn't overlap.
    back_to_back = make_type(db, total=5)
    reserved(db, make_event_at(db, STARTS - timedelta(hours=2), STARTS), back_to_back, 5)
    line = make_line(db, event, back_to_back, 5)
    assert (await client.post(reservation_url(line.id), headers=auth(tech))).status_code == 201

    # A venue's turnaround: an event ending 10 minutes before this one, at a venue with a 30-minute
    # turnaround, holds all 5. Equipment goes by the events' own times, so it doesn't count (AC 1).
    buffered = make_type(db, total=5)
    earlier = make_event_at(db, STARTS - timedelta(hours=2), STARTS - timedelta(minutes=10))
    booking = make_venue_booking(
        db, event=earlier, venue=make_venue(db, turnaround_minutes=30), user=make_user(db, UserRole.COORDINATOR),
        starts_at=earlier.start_at, ends_at=earlier.end_at,
    )
    assert booking.occupied_ends_at > STARTS
    reserved(db, earlier, buffered, 5)
    line = make_line(db, event, buffered, 5)
    assert (await client.post(reservation_url(line.id), headers=auth(tech))).status_code == 201


async def test_tc_us27_09_a_reservation_reduces_overlapping_events_availability(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    webcams = make_type(db, total=8)
    await client.post(reservation_url(make_line(db, event, webcams, 3).id), headers=auth(tech))
    overlapping = make_line(db, make_event_at(db, STARTS + timedelta(hours=1), ENDS), webcams, 1, EquipmentLineStatus.PENDING)
    apart = make_line(db, make_event_at(db, ENDS, ENDS + timedelta(hours=2)), webcams, 1, EquipmentLineStatus.PENDING)

    overlapping_check = (await client.post(check_url(overlapping.id), headers=auth(tech))).json()
    apart_check = (await client.post(check_url(apart.id), headers=auth(tech))).json()

    assert (overlapping_check["reserved_elsewhere"], overlapping_check["available"]) == (3, 5)
    assert (apart_check["reserved_elsewhere"], apart_check["available"]) == (0, 8)


@pytest.mark.parametrize(
    ("case", "status", "code"),
    [
        ("pending", 409, "LINE_NOT_APPROVED"),
        ("rejected", 409, "LINE_NOT_APPROVED"),
        ("reserved", 409, "ALREADY_RESERVED"),
        ("event not eligible", 409, "EVENT_NOT_ELIGIBLE"),
    ],
)
async def test_tc_us27_10_only_an_unreserved_approved_line_on_an_eligible_event(
    client: AsyncClient, db: Session, tech: User, event: Event, case: str, status: int, code: str
) -> None:
    equipment_type = make_type(db)
    if case == "pending":
        line = make_line(db, event, equipment_type, 2, EquipmentLineStatus.PENDING)
    elif case == "rejected":
        line = make_line(db, event, equipment_type, 2, EquipmentLineStatus.REJECTED)
    elif case == "reserved":
        line = db.get(EquipmentRequestLine, reserved(db, event, equipment_type, 2).request_line_id)
    else:
        # D76: approved, but its event is past planning and confirmed.
        line = make_line(db, make_event_at(db, STARTS, ENDS, status=EventStatus.COMPLETED), equipment_type, 2)
    before = reservation_count(db)

    response = await client.post(reservation_url(line.id), headers=auth(tech))

    assert response.status_code == status
    assert response.json()["code"] == code
    assert reservation_count(db) == before


async def test_tc_us27_12_release_returns_the_units(client: AsyncClient, db: Session, tech: User, event: Event) -> None:
    laptops = make_type(db, total=4)
    line = make_line(db, event, laptops, 4)
    await client.post(reservation_url(line.id), headers=auth(tech))
    rival = make_line(db, make_event_at(db, STARTS, ENDS), laptops, 4, EquipmentLineStatus.PENDING)
    assert (await client.post(check_url(rival.id), headers=auth(tech))).json()["available"] == 0

    response = await client.delete(reservation_url(line.id), headers=auth(tech))

    assert response.status_code == 204
    assert reservation_count(db) == 0
    assert (await client.post(check_url(rival.id), headers=auth(tech))).json()["available"] == 4
    # And it can be reserved again (AC 5).
    assert (await client.post(reservation_url(line.id), headers=auth(tech))).status_code == 201


async def test_tc_us27_12_releasing_an_unreserved_line_is_refused(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    line = make_line(db, event, make_type(db), 2)

    response = await client.delete(reservation_url(line.id), headers=auth(tech))

    assert response.status_code == 409
    assert response.json()["code"] == "NOT_RESERVED"


async def test_tc_us27_13_a_cancelled_events_reservation_counts_as_released(
    client: AsyncClient, db: Session, tech: User, event: Event
) -> None:
    # D75: nothing cancels an event yet (US9); a cancelled event's reservations stop counting.
    tablets = make_type(db, total=4)
    cancelled_event = make_event_at(db, STARTS, ENDS)
    held = reserved(db, cancelled_event, tablets, 4)
    cancelled_event.status = EventStatus.CANCELLED
    db.flush()
    pending = make_line(db, event, tablets, 4, EquipmentLineStatus.PENDING)
    other = make_line(db, make_event_at(db, STARTS, ENDS), tablets, 4)

    check = (await client.post(check_url(pending.id), headers=auth(tech))).json()
    reserve = await client.post(reservation_url(other.id), headers=auth(tech))
    approved = (await client.get(QUEUE_URL, headers=auth(tech), params={"status": "approved"})).json()["lines"]

    assert (check["reserved_elsewhere"], check["available"]) == (0, 4)
    assert reserve.status_code == 201
    [released] = [line for line in approved if line["id"] == str(held.request_line_id)]
    assert released["reservation"]["released_because_event_cancelled"] is True


async def test_tc_us27_14_lines_show_their_reservation(client: AsyncClient, db: Session, tech: User, event: Event) -> None:
    line = make_line(db, event, make_type(db), 2)
    unreserved = make_line(db, event, make_type(db), 1)
    await client.post(reservation_url(line.id), headers=auth(tech))
    coordinator = db.get(User, event.coordinator_id)

    approved = (await client.get(QUEUE_URL, headers=auth(tech), params={"status": "approved"})).json()["lines"]
    own = (await client.get(f"/api/v1/events/{event.id}/equipment-lines", headers=auth(coordinator))).json()["lines"]

    for listing in (approved, own):
        by_id = {item["id"]: item for item in listing}
        assert by_id[str(line.id)]["reservation"]["quantity"] == 2
        assert by_id[str(line.id)]["reservation"]["reserved_by_user_id"] == str(tech.id)
        assert by_id[str(unreserved.id)]["reservation"] is None
    # The approved list holds approved lines only.
    assert {item["status"] for item in approved} == {"approved"}


@pytest.mark.parametrize("role", [role for role in UserRole if role != UserRole.TECH_SUPPORT])
async def test_tc_us27_15_only_tech_support_reserves_and_releases(
    client: AsyncClient, db: Session, event: Event, role: UserRole
) -> None:
    line = make_line(db, event, make_type(db), 1)
    user = make_user(db, role)

    for response in (
        await client.post(reservation_url(line.id), headers=auth(user)),
        await client.delete(reservation_url(line.id), headers=auth(user)),
    ):
        assert response.status_code == 403
        assert response.json() == {"code": "FORBIDDEN"}
    assert reservation_count(db) == 0


async def test_tc_us27_15_identity_and_unknown_lines(client: AsyncClient, db: Session, tech: User, event: Event) -> None:
    line = make_line(db, event, make_type(db), 1)

    for response in (await client.post(reservation_url(line.id)), await client.delete(reservation_url(line.id))):
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"
    for response in (
        await client.post(reservation_url(uuid.uuid4()), headers=auth(tech)),
        await client.delete(reservation_url(uuid.uuid4()), headers=auth(tech)),
    ):
        assert response.status_code == 404
        assert response.json() == {"code": "NOT_FOUND"}


# --- TC-US27-11 two reservations at the same moment ---


class Committed:
    """Rows committed for real, so two sessions on separate connections both see them."""

    def __init__(self, tech: uuid.UUID, lines: list[uuid.UUID], ids: dict[str, list[uuid.UUID]]) -> None:
        self.tech, self.lines, self.ids = tech, lines, ids

    def reserve(self, engine: Engine, line_id: uuid.UUID) -> object:
        """One reservation in its own session: 201, or the refusal's (status, code)."""
        with Session(engine) as session:
            try:
                equipment_service.reserve(session, session.get(User, self.tech), line_id)
                return 201
            except DomainError as error:
                return (error.status_code, error.code)


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    """The `db` fixture's rows are in one uncommitted transaction, invisible to other connections, so
    this commits its own and deletes them afterwards (as TC-US22-15 does)."""
    with Session(engine) as setup:
        tech = make_user(setup, UserRole.TECH_SUPPORT)
        only_one = make_type(setup, total=3)
        events = [make_event_at(setup, STARTS, ENDS), make_event_at(setup, STARTS + timedelta(hours=1), ENDS)]
        lines = [make_line(setup, e, only_one, 3) for e in events]
        setup.commit()
        user_ids = [tech.id] + [e.coordinator_id for e in events] + [line.reviewed_by_user_id for line in lines]
        rows = Committed(
            tech.id,
            [line.id for line in lines],
            {"users": user_ids, "events": [e.id for e in events], "types": [only_one.id]},
        )
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(EquipmentReservation).where(EquipmentReservation.request_line_id.in_(rows.lines)))
            cleanup.execute(delete(EquipmentRequestLine).where(EquipmentRequestLine.id.in_(rows.lines)))
            cleanup.execute(delete(Event).where(Event.id.in_(rows.ids["events"])))
            cleanup.execute(delete(EquipmentType).where(EquipmentType.id.in_(rows.ids["types"])))
            cleanup.execute(delete(User).where(User.id.in_(rows.ids["users"])))
            cleanup.commit()


def test_tc_us27_11_two_reservations_for_the_last_units_only_one_wins(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real race: both sessions have their line in hand and wait at a barrier just before locking the
    type, then both go. The type's lock makes the second wait for the first's commit and count it, so
    only one reservation fits (AC 2). Without the lock both would see 3 free and both would reserve."""
    barrier = threading.Barrier(2, timeout=10)
    original = equipment_service_module._lock_type

    def wait_then_lock(*args: object, **kwargs: object) -> object:
        barrier.wait()
        return original(*args, **kwargs)

    monkeypatch.setattr(equipment_service_module, "_lock_type", wait_then_lock)
    outcomes: list[object] = []
    threads = [
        threading.Thread(target=lambda line=line: outcomes.append(committed.reserve(engine, line)))
        for line in committed.lines
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes, key=str) == sorted([201, (409, "INSUFFICIENT_EQUIPMENT")], key=str)
    with Session(engine) as check:
        count = select(func.count()).where(EquipmentReservation.request_line_id.in_(committed.lines))
        assert check.scalar(count) == 1
