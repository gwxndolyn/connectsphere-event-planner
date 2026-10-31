"""US14 Tech support staff, PR 2 (SCRUM-134, story SCRUM-17): the event's coordinator lists, assigns and
unassigns Tech support staff, and each person assigned is notified. The table is PR 1's
(test_tech_staff_schema.py); see docs/testing/US14-tech-support-staff.md."""

import threading
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

import app.equipment.tech_staff_service as tech_staff_module
from app.core.clock import get_now
from app.core.exceptions import DomainError
from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentType, TechStaffAssignment
from app.equipment.tech_staff_service import tech_staff_service
from app.event.models import Event, EventStatus
from app.main import app
from app.notification.service import notifier as logging_notifier
from app.user.models import User, UserRole
from app.venue.models import VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.equipment.test_equipment_reservation_api import make_event_at, make_line, make_type
from tests.factories import NOW, make_user, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

# The event: 10:00 to 13:00, three days after NOW.
STARTS = NOW.replace(hour=10) + timedelta(days=3)
ENDS = STARTS + timedelta(hours=3)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def staff_url(event_id: uuid.UUID) -> str:
    return f"/api/v1/events/{event_id}/tech-staff"


def one_url(event_id: uuid.UUID, staff_user_id: uuid.UUID) -> str:
    return f"{staff_url(event_id)}/{staff_user_id}"


def eligible_event(db: Session, start_at: datetime = STARTS, end_at: datetime = ENDS, **fields) -> Event:
    """A confirmed event with one approved equipment line: an approved technical support request (AC 1)."""
    event = make_event_at(db, start_at, end_at, **fields)
    make_line(db, event, make_type(db), 1)
    return event


def tech(db: Session, active: bool = True) -> User:
    user = make_user(db, UserRole.TECH_SUPPORT, active=active)
    user.full_name = f"Tech {user.id.hex[:6]}"
    db.flush()
    return user


def coordinator_of(db: Session, event: Event) -> User:
    return db.get(User, event.coordinator_id)


def assigned_elsewhere(db: Session, staff: User, start_at: datetime, end_at: datetime, unassigned: bool = False) -> Event:
    """`staff` assigned to another event at those times, and since unassigned if `unassigned`."""
    other = make_event_at(db, start_at, end_at)
    row = TechStaffAssignment(
        event_id=other.id, staff_user_id=staff.id, assigned_by_user_id=other.coordinator_id, assigned_at=NOW
    )
    if unassigned:
        row.unassigned_at, row.unassigned_by_user_id = NOW, other.coordinator_id
    db.add(row)
    db.flush()
    return other


def active_tech_ids(db: Session) -> set[str]:
    query = select(User.id).where(User.roles.any(UserRole.TECH_SUPPORT), User.is_active.is_(True))
    return {str(user_id) for user_id in db.scalars(query)}


def ids(people: list[dict]) -> set[str]:
    return {person["id"] for person in people}


def assignment_count(db: Session, event: Event) -> int:
    return db.scalar(select(func.count()).where(TechStaffAssignment.event_id == event.id))


@pytest.fixture
def event(db: Session) -> Event:
    return eligible_event(db)


async def test_tc_us14_05_an_eligible_event_lists_every_active_tech_support_user(
    client: AsyncClient, db: Session, event: Event
) -> None:
    tech(db)
    tech(db)
    inactive = tech(db, active=False)

    response = await client.get(staff_url(event.id), headers=auth(coordinator_of(db, event)))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["eligible"] is True
    assert (body["assigned"], body["log"]) == ([], [])
    assert ids(body["available"]) == active_tech_ids(db)
    assert str(inactive.id) not in ids(body["available"])


@pytest.mark.parametrize("case", ["no lines", "pending", "rejected", "completed", "cancelled"])
async def test_tc_us14_06_without_an_approved_request_nobody_can_be_assigned(
    client: AsyncClient, db: Session, case: str
) -> None:
    if case in ("completed", "cancelled"):
        # D80: approved, but the event is past planning and confirmed.
        event = eligible_event(db, status=EventStatus(case))
    else:
        event = make_event_at(db, STARTS, ENDS)
        if case != "no lines":
            make_line(db, event, make_type(db), 1, EquipmentLineStatus(case))
    coordinator = coordinator_of(db, event)

    listed = (await client.get(staff_url(event.id), headers=auth(coordinator))).json()
    response = await client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(tech(db).id)]})

    assert listed["eligible"] is False
    assert (response.status_code, response.json()) == (409, {"code": "NO_APPROVED_TECH_REQUEST"})
    assert assignment_count(db, event) == 0


async def test_tc_us14_07_staff_on_an_overlapping_event_are_unavailable(
    client: AsyncClient, db: Session, event: Event
) -> None:
    busy, back_to_back, other_day, freed = tech(db), tech(db), tech(db), tech(db)
    assigned_elsewhere(db, busy, STARTS + timedelta(hours=1), ENDS + timedelta(hours=1))
    # D81: the events' own times, so ending as this one starts doesn't overlap.
    assigned_elsewhere(db, back_to_back, STARTS - timedelta(hours=2), STARTS)
    assigned_elsewhere(db, other_day, STARTS + timedelta(days=1), ENDS + timedelta(days=1))
    assigned_elsewhere(db, freed, STARTS, ENDS, unassigned=True)
    coordinator = coordinator_of(db, event)

    available = ids((await client.get(staff_url(event.id), headers=auth(coordinator))).json()["available"])
    response = await client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(busy.id)]})

    assert str(busy.id) not in available
    assert {str(back_to_back.id), str(other_day.id), str(freed.id)} <= available
    assert (response.status_code, response.json()) == (409, {"code": "STAFF_UNAVAILABLE", "staff_user_ids": [str(busy.id)]})
    assert assignment_count(db, event) == 0


async def test_tc_us14_08_several_staff_are_assigned_at_once(client: AsyncClient, db: Session, event: Event) -> None:
    first, second = tech(db), tech(db)
    coordinator = coordinator_of(db, event)

    response = await client.post(
        staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(first.id), str(second.id)]}
    )

    assert response.status_code == 201, response.text
    assigned = response.json()["assigned"]
    assert {item["staff"]["id"] for item in assigned} == {str(first.id), str(second.id)}
    assert all(item["assigned_by"]["id"] == str(coordinator.id) and item["assigned_at"] for item in assigned)
    rows = db.scalars(select(TechStaffAssignment).where(TechStaffAssignment.event_id == event.id)).all()
    assert {(row.staff_user_id, row.assigned_by_user_id, row.unassigned_at) for row in rows} == {
        (first.id, coordinator.id, None),
        (second.id, coordinator.id, None),
    }


async def test_tc_us14_08_one_unavailable_and_nobody_is_assigned(client: AsyncClient, db: Session, event: Event) -> None:
    free, busy = tech(db), tech(db)
    assigned_elsewhere(db, busy, STARTS, ENDS)

    response = await client.post(
        staff_url(event.id), headers=auth(coordinator_of(db, event)), json={"staff_user_ids": [str(free.id), str(busy.id)]}
    )

    assert (response.status_code, response.json()) == (409, {"code": "STAFF_UNAVAILABLE", "staff_user_ids": [str(busy.id)]})
    assert assignment_count(db, event) == 0


async def test_tc_us14_09_each_person_assigned_is_notified_with_the_primary_venue(
    client: AsyncClient, db: Session, notifier: FakeNotifier, event: Event
) -> None:
    event.equipment_needs = "Two lapel mics for the panel"
    [first_line] = db.scalars(select(EquipmentRequestLine).where(EquipmentRequestLine.event_id == event.id)).all()
    first_type = db.get(EquipmentType, first_line.equipment_type_id)
    projector = make_type(db)
    make_line(db, event, projector, 2)
    # Not approved, so not a requirement.
    make_line(db, event, make_type(db), 5, EquipmentLineStatus.PENDING)
    coordinator = coordinator_of(db, event)
    hall = make_venue(db, name="Hall A", location="Building 1, Level 2")
    make_venue_booking(
        db, event=event, venue=hall, user=coordinator, starts_at=STARTS, ends_at=ENDS,
        status=VenueBookingStatus.APPROVED, is_primary=True,
    )
    first, second = tech(db), tech(db)

    response = await client.post(
        staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(first.id), str(second.id)]}
    )

    assert response.status_code == 201, response.text
    expected = {
        "event_id": event.id,
        "event_name": event.name,
        "starts_at": STARTS,
        "ends_at": ENDS,
        "venue_name": "Hall A",
        "location": "Building 1, Level 2",
        "equipment": sorted([f"1 x {first_type.name}", f"2 x {projector.name}"]),
        "equipment_needs": "Two lapel mics for the panel",
    }
    assert sorted(notifier.tech_staff_assignments, key=lambda call: call["email"]) == sorted(
        [expected | {"email": first.email}, expected | {"email": second.email}], key=lambda call: call["email"]
    )


async def test_tc_us14_09_without_a_primary_venue_the_events_own_is_sent(
    client: AsyncClient, db: Session, notifier: FakeNotifier, event: Event
) -> None:
    staff = tech(db)

    await client.post(staff_url(event.id), headers=auth(coordinator_of(db, event)), json={"staff_user_ids": [str(staff.id)]})

    [call] = notifier.tech_staff_assignments
    # D70: the event's own venue_name and room_number (the factory's).
    assert (call["venue_name"], call["location"]) == ("SMU SCIS Building", "Seminar Room 2-1")
    assert call["equipment_needs"] is None


async def test_tc_us14_09_a_notifier_failure_keeps_the_assignment(
    client: AsyncClient, db: Session, notifier: FakeNotifier, event: Event
) -> None:
    notifier.fail = True
    staff = tech(db)

    response = await client.post(
        staff_url(event.id), headers=auth(coordinator_of(db, event)), json={"staff_user_ids": [str(staff.id)]}
    )

    assert response.status_code == 201
    assert assignment_count(db, event) == 1


async def test_tc_us14_10_unassign_then_assign_someone_else(client: AsyncClient, db: Session, event: Event) -> None:
    first, second = tech(db), tech(db)
    coordinator = coordinator_of(db, event)
    await client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(first.id)]})

    unassigned = await client.delete(one_url(event.id, first.id), headers=auth(coordinator))
    listed = (await client.get(staff_url(event.id), headers=auth(coordinator))).json()
    reassigned = await client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(second.id)]})

    assert unassigned.status_code == 204
    assert listed["assigned"] == []
    assert str(first.id) in ids(listed["available"])
    assert reassigned.status_code == 201
    assert [item["staff"]["id"] for item in reassigned.json()["assigned"]] == [str(second.id)]
    row = db.scalars(select(TechStaffAssignment).where(TechStaffAssignment.staff_user_id == first.id)).one()
    assert (row.unassigned_by_user_id, row.unassigned_at) == (coordinator.id, NOW)


@pytest.mark.parametrize("starts", [NOW, NOW - timedelta(hours=1)], ids=["starting now", "under way"])
async def test_tc_us14_10_nothing_changes_once_the_event_has_started(
    client: AsyncClient, db: Session, starts: datetime
) -> None:
    event = eligible_event(db, starts, starts + timedelta(hours=3))
    on_duty = tech(db)
    db.add(TechStaffAssignment(event_id=event.id, staff_user_id=on_duty.id, assigned_by_user_id=event.coordinator_id))
    db.flush()
    coordinator = coordinator_of(db, event)

    assign = await client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(tech(db).id)]})
    unassign = await client.delete(one_url(event.id, on_duty.id), headers=auth(coordinator))

    for response in (assign, unassign):
        assert (response.status_code, response.json()) == (409, {"code": "EVENT_STARTED"})
    rows = db.scalars(select(TechStaffAssignment).where(TechStaffAssignment.event_id == event.id)).all()
    assert [(row.staff_user_id, row.unassigned_at) for row in rows] == [(on_duty.id, None)]


async def test_tc_us14_11_the_log_has_every_assign_and_unassign_newest_first(
    client: AsyncClient, db: Session, event: Event
) -> None:
    first, second = tech(db), tech(db)
    coordinator = coordinator_of(db, event)
    for minutes, call in (
        (0, lambda: client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(first.id)]})),
        (1, lambda: client.delete(one_url(event.id, first.id), headers=auth(coordinator))),
        (2, lambda: client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(second.id)]})),
    ):
        app.dependency_overrides[get_now] = lambda minutes=minutes: NOW + timedelta(minutes=minutes)
        assert (await call()).status_code in (201, 204)

    log = (await client.get(staff_url(event.id), headers=auth(coordinator))).json()["log"]

    by = {"id": str(coordinator.id), "name": coordinator.display_name}
    assert [(entry["action"], entry["staff"], entry["by"], datetime.fromisoformat(entry["at"])) for entry in log] == [
        ("assigned", {"id": str(second.id), "name": second.full_name}, by, NOW + timedelta(minutes=2)),
        ("unassigned", {"id": str(first.id), "name": first.full_name}, by, NOW + timedelta(minutes=1)),
        ("assigned", {"id": str(first.id), "name": first.full_name}, by, NOW),
    ]


@pytest.mark.parametrize("who", ["not tech support", "inactive", "unknown"])
async def test_tc_us14_12_only_active_tech_support_can_be_assigned(
    client: AsyncClient, db: Session, event: Event, who: str
) -> None:
    if who == "not tech support":
        invalid = make_user(db, UserRole.COORDINATOR).id
    elif who == "inactive":
        invalid = tech(db, active=False).id
    else:
        invalid = uuid.uuid4()

    response = await client.post(
        staff_url(event.id), headers=auth(coordinator_of(db, event)), json={"staff_user_ids": [str(tech(db).id), str(invalid)]}
    )

    assert (response.status_code, response.json()) == (422, {"code": "INVALID_STAFF", "staff_user_ids": [str(invalid)]})
    assert assignment_count(db, event) == 0


async def test_tc_us14_12_already_assigned_and_not_assigned(client: AsyncClient, db: Session, event: Event) -> None:
    staff, never = tech(db), tech(db)
    coordinator = coordinator_of(db, event)
    await client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(staff.id)]})

    again = await client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": [str(staff.id)]})
    unassign = await client.delete(one_url(event.id, never.id), headers=auth(coordinator))
    empty = await client.post(staff_url(event.id), headers=auth(coordinator), json={"staff_user_ids": []})

    assert (again.status_code, again.json()) == (409, {"code": "ALREADY_ASSIGNED", "staff_user_ids": [str(staff.id)]})
    assert (unassign.status_code, unassign.json()) == (409, {"code": "NOT_ASSIGNED"})
    assert empty.status_code == 422
    assert assignment_count(db, event) == 1


@pytest.mark.parametrize("role", [role for role in UserRole if role != UserRole.COORDINATOR])
async def test_tc_us14_14_only_coordinators_list_assign_and_unassign(
    client: AsyncClient, db: Session, event: Event, role: UserRole
) -> None:
    staff, user = tech(db), make_user(db, role)

    for response in (
        await client.get(staff_url(event.id), headers=auth(user)),
        await client.post(staff_url(event.id), headers=auth(user), json={"staff_user_ids": [str(staff.id)]}),
        await client.delete(one_url(event.id, staff.id), headers=auth(user)),
    ):
        assert (response.status_code, response.json()) == (403, {"code": "FORBIDDEN"})
    assert assignment_count(db, event) == 0


async def test_tc_us14_14_another_coordinator_no_identity_and_unknown_events(
    client: AsyncClient, db: Session, event: Event
) -> None:
    staff = tech(db)
    body = {"staff_user_ids": [str(staff.id)]}
    other = make_user(db, UserRole.COORDINATOR)

    for headers, event_id, expected in (
        (auth(other), event.id, (404, {"code": "NOT_FOUND"})),
        ({}, event.id, (401, {"code": "UNAUTHENTICATED"})),
        (auth(coordinator_of(db, event)), uuid.uuid4(), (404, {"code": "NOT_FOUND"})),
    ):
        for response in (
            await client.get(staff_url(event_id), headers=headers),
            await client.post(staff_url(event_id), headers=headers, json=body),
            await client.delete(one_url(event_id, staff.id), headers=headers),
        ):
            assert (response.status_code, response.json()) == expected
    assert assignment_count(db, event) == 0


# --- TC-US14-13 two coordinators assign the same person at the same moment ---


class Committed:
    """Rows committed for real, so two sessions on separate connections both see them."""

    def __init__(self, staff: uuid.UUID, events: list[uuid.UUID], ids: dict[str, list[uuid.UUID]]) -> None:
        self.staff, self.events, self.ids = staff, events, ids

    def assign(self, engine: Engine, event_id: uuid.UUID) -> object:
        """One assignment by the event's coordinator in its own session: 201, or the refusal's (status, code)."""
        with Session(engine) as session:
            coordinator = session.get(User, session.get(Event, event_id).coordinator_id)
            try:
                tech_staff_service.assign(session, coordinator, event_id, [self.staff], NOW, logging_notifier)
                return 201
            except DomainError as error:
                return (error.status_code, error.code)


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    """The `db` fixture's rows are in one uncommitted transaction, invisible to other connections, so
    this commits its own and deletes them afterwards (as TC-US27-11 does)."""
    with Session(engine) as setup:
        staff = tech(setup)
        equipment_type = make_type(setup)
        events = [make_event_at(setup, STARTS, ENDS), make_event_at(setup, STARTS + timedelta(hours=1), ENDS)]
        lines = [make_line(setup, e, equipment_type, 1) for e in events]
        setup.commit()
        user_ids = [staff.id] + [e.coordinator_id for e in events] + [line.reviewed_by_user_id for line in lines]
        rows = Committed(
            staff.id,
            [e.id for e in events],
            {"users": user_ids, "lines": [line.id for line in lines], "types": [equipment_type.id]},
        )
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(TechStaffAssignment).where(TechStaffAssignment.event_id.in_(rows.events)))
            cleanup.execute(delete(EquipmentRequestLine).where(EquipmentRequestLine.id.in_(rows.ids["lines"])))
            cleanup.execute(delete(Event).where(Event.id.in_(rows.events)))
            cleanup.execute(delete(EquipmentType).where(EquipmentType.id.in_(rows.ids["types"])))
            cleanup.execute(delete(User).where(User.id.in_(rows.ids["users"])))
            cleanup.commit()


def test_tc_us14_13_two_coordinators_assign_the_same_person_only_one_wins(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real race: both sessions have checked their event and wait at a barrier just before locking the
    staff member's row, then both go. The lock makes the second wait for the first's commit and see that
    assignment, so the person isn't on two overlapping events (AC 2). Without it both would see them free."""
    barrier = threading.Barrier(2, timeout=10)
    original = tech_staff_module._lock_staff

    def wait_then_lock(*args: object, **kwargs: object) -> object:
        barrier.wait()
        return original(*args, **kwargs)

    monkeypatch.setattr(tech_staff_module, "_lock_staff", wait_then_lock)
    outcomes: list[object] = []
    threads = [
        threading.Thread(target=lambda event_id=event_id: outcomes.append(committed.assign(engine, event_id)))
        for event_id in committed.events
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes, key=str) == sorted([201, (409, "STAFF_UNAVAILABLE")], key=str)
    with Session(engine) as check:
        count = select(func.count()).where(
            TechStaffAssignment.staff_user_id == committed.staff, TechStaffAssignment.unassigned_at.is_(None)
        )
        assert check.scalar(count) == 1
