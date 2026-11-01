"""US29b review an event change request, PR 2 (SCRUM-142, story SCRUM-98): the review flags an approved
significant change raises (D104), listed and cleared by the event's coordinator; an open flag keeps the event from
being confirmed. See docs/testing/US29b-change-request-review.md (TC-US29B-22, 25)."""

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

import app.event.review_flag_service as flag_module
from app.core.exceptions import DomainError
from app.equipment.models import EquipmentLineStatus, EquipmentReservation
from app.event.change_decision_schemas import ClearFlagWrite
from app.event.models import Event, EventReviewFlag
from app.event.review_flag_service import review_flag_service
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBookingStatus
from tests.equipment.test_equipment_api import make_line
from tests.equipment.test_equipment_schema import make_type
from tests.event.test_change_request_decisions import (  # noqa: F401 - committed is a fixture
    Committed,
    approve,
    change,
    committed,
    confirmed_event,
    move,
    pending,
    reassign_from,
)
from tests.event.test_confirmation import book, reserve
from tests.event.test_event_request_clarification_api import auth
from tests.factories import NOW, make_user, make_venue

pytestmark = pytest.mark.anyio


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def venue_staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def tech(db: Session) -> User:
    return make_user(db, UserRole.TECH_SUPPORT)


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db, name="SCIS Seminar Room 2-1", capacity=60)


@pytest.fixture
def flagged(client: AsyncClient, db: Session, organiser: User, coordinator: User, venue: Venue, venue_staff: User) -> Event:
    """A Confirmed event with one approved booking, moved an hour later: back in Planning, its booking flagged."""
    event = confirmed_event(db, organiser, coordinator)
    book(db, event, venue, coordinator, venue_staff, starts_at=event.start_at, ends_at=event.end_at)
    return event


async def move_it(client: AsyncClient, db: Session, event: Event, organiser: User, coordinator: User, changes=None) -> None:
    response = await approve(client, coordinator, pending(db, event, organiser, changes or move(event)))
    assert response.status_code == 200, response.text


async def listed(client: AsyncClient, user: User, event: Event):
    return await client.get(f"/api/v1/events/{event.id}/review-flags", headers=auth(user))


async def clear(client: AsyncClient, user: User, flag_id, note: object = None):
    return await client.post(f"/api/v1/review-flags/{flag_id}/clear", headers=auth(user), json={"note": note})


# --- TC-US29B-22 the coordinator reviews and clears flags; open ones block confirming (AC 3, D104) ---


async def test_tc_us29b_22_the_coordinator_clears_a_flag_and_open_flags_block_confirming(
    client: AsyncClient, db: Session, flagged: Event, organiser: User, coordinator: User
) -> None:
    await move_it(client, db, flagged, organiser, coordinator)
    [flag] = (await listed(client, coordinator, flagged)).json()["flags"]
    assert (flag["kind"], flag["open"], flag["resolved"], flag["fields"]) == ("venue_booking", True, False, ["start_at", "end_at"])
    assert "SCIS Seminar Room 2-1" in flag["target"]["label"]

    readiness = (await client.get(f"/api/v1/event-requests/{flagged.id}/readiness", headers=auth(coordinator))).json()
    item = next(i for i in readiness["items"] if i["kind"] == "review_flags")
    assert item["complete"] is False
    confirm = await client.post(f"/api/v1/event-requests/{flagged.id}/confirmation", headers=auth(coordinator))
    assert confirm.status_code == 409 and "review_flags" in [i["kind"] for i in confirm.json()["outstanding"]]

    too_long = await clear(client, coordinator, flag["id"], note="x" * 1001)
    other = await clear(client, make_user(db, UserRole.COORDINATOR), flag["id"])
    wrong_role = await clear(client, organiser, flag["id"])
    cleared = await clear(client, coordinator, flag["id"], note="Venue staff confirmed the later slot.")
    again = await clear(client, coordinator, flag["id"])

    assert too_long.status_code == 422 and too_long.json()["code"] == "INVALID_REVIEW_FLAG"
    assert (other.status_code, other.json()) == (404, {"code": "NOT_FOUND"})
    assert wrong_role.status_code == 403
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert (body["open"], body["cleared_note"], body["cleared_by"]["id"]) == (False, "Venue staff confirmed the later slot.", str(coordinator.id))
    assert (again.status_code, again.json()) == (409, {"code": "FLAG_ALREADY_CLEARED"})
    readiness = (await client.get(f"/api/v1/event-requests/{flagged.id}/readiness", headers=auth(coordinator))).json()
    assert next(i for i in readiness["items"] if i["kind"] == "review_flags")["complete"] is True


async def test_tc_us29b_22_an_event_never_flagged_has_no_review_item_and_others_cannot_list_flags(
    client: AsyncClient, db: Session, organiser: User, coordinator: User
) -> None:
    event = confirmed_event(db, organiser, coordinator)
    readiness = (await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(coordinator))).json()
    assert "review_flags" not in [i["kind"] for i in readiness["items"]]
    assert (await listed(client, coordinator, event)).json() == {"flags": []}
    assert (await listed(client, make_user(db, UserRole.COORDINATOR), event)).status_code == 404
    assert (await listed(client, organiser, event)).status_code == 403


async def test_tc_us29b_22_a_withdrawn_booking_or_released_reservation_reads_as_resolved(
    client: AsyncClient, db: Session, organiser: User, coordinator: User, venue: Venue, venue_staff: User, tech: User
) -> None:
    """D104: derived on read; nothing writes a clearance (unclear point 2)."""
    event = confirmed_event(db, organiser, coordinator)
    booking = book(db, event, venue, coordinator, venue_staff, starts_at=event.start_at, ends_at=event.end_at)
    line = make_line(db, event=event, equipment_type=make_type(db), requested_by=coordinator,
                     status=EquipmentLineStatus.APPROVED, reviewer=tech)
    reservation = reserve(db, line, tech)
    await move_it(client, db, event, organiser, coordinator, changes=[change(event, "equipment_needs", "Two projectors"),
                                                                       change(event, "room_layout_preference", "Cabaret")])
    booking.status, booking.withdrawn_at = VenueBookingStatus.WITHDRAWN, NOW
    db.execute(delete(EquipmentReservation).where(EquipmentReservation.id == reservation.id))
    db.flush()

    flags = (await listed(client, coordinator, event)).json()["flags"]

    assert {(f["kind"], f["resolved"], f["open"], f["cleared_at"]) for f in flags} == {
        ("venue_booking", True, False, None), ("equipment_reservation", True, False, None)
    }
    readiness = (await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(coordinator))).json()
    assert next(i for i in readiness["items"] if i["kind"] == "review_flags")["complete"] is True
    stored = db.scalars(select(EventReviewFlag).where(EventReviewFlag.event_id == event.id)).all()
    assert all(f.cleared_at is None for f in stored)


# --- TC-US29B-25 one open flag per item: a later change adds its fields (D104) ---


async def test_tc_us29b_25_a_second_change_adds_its_fields_to_the_open_flag(
    client: AsyncClient, db: Session, flagged: Event, organiser: User, coordinator: User
) -> None:
    await move_it(client, db, flagged, organiser, coordinator)
    db.refresh(flagged)
    await move_it(client, db, flagged, organiser, coordinator, changes=[change(flagged, "expected_attendees", 45)])

    stored = db.scalars(select(EventReviewFlag).where(
        EventReviewFlag.event_id == flagged.id, EventReviewFlag.kind == "venue_booking"
    )).all()

    assert len(stored) == 1
    assert stored[0].fields == ["start_at", "end_at", "expected_attendees"]


# --- Calvin's #125 review, note 1: a reassignment just before the lock refuses the old coordinator's clear ---


def test_tc_us29b_22_a_reassignment_just_before_the_lock_refuses_the_old_coordinators_clear(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first check passes on the event as read; a Lead then reassigns it on another connection and commits,
    before the clear locks anything. The check made again on the locked event refuses the old coordinator."""
    original = flag_module.is_assigned_coordinator
    calls = {"n": 0}

    def check_then_reassign(event: Event, user: User) -> bool:
        allowed = original(event, user)
        calls["n"] += 1
        if calls["n"] == 1:
            reassign_from(engine, committed)
        return allowed

    monkeypatch.setattr(flag_module, "is_assigned_coordinator", check_then_reassign)
    flag_id = committed.ids["flag"][0]

    with Session(engine) as session:
        coordinator = session.get(User, committed.ids["coordinator"][0])
        try:
            review_flag_service.clear(session, coordinator, flag_id, ClearFlagWrite(note="Checked."), NOW)
            outcome: object = 200
        except DomainError as error:
            outcome = (error.status_code, error.code)

    assert outcome == (404, "NOT_FOUND")
    with Session(engine) as check:
        assert check.get(EventReviewFlag, flag_id).cleared_at is None
