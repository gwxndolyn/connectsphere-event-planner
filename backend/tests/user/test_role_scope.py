"""US16b role-based access, PR 2 (SCRUM-120, story SCRUM-82): coordinators see and act only on the
requests assigned to them (D48), organisers only on their own (D47), attendees on nothing internal
(AC 6), every role-gated route refuses the roles it doesn't name (AC 3), Leads see their own
assignments (AC 7), and no one decides a record they created (D51). Venue Staff no longer read
event requests (decided 25 Oct). See docs/testing/US16b-role-based-access.md."""

import uuid
from collections.abc import Iterator
from datetime import timedelta

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentLineStatus
from app.event.models import Event, EventRequestClarification, EventStatus
from app.main import app
from app.seed import seed
from app.user.models import User, UserRole
from app.venue.models import VenueBookingStatus
from tests.conftest import BACKEND_DIR, FakeNotifier
from tests.equipment.test_equipment_api import make_line, make_type
from tests.event.test_event_requests import complete_request
from tests.factories import NOW, make_attendee, make_event, make_registration, make_user, make_venue, make_venue_booking

pytestmark = pytest.mark.anyio

REVISION = "20261030_1200_us16b_d51_checks"
QUESTION = {"sections": ["attendance"], "comment": "How many people are coming?"}
FORBIDDEN = {"code": "FORBIDDEN"}
NOT_FOUND = {"code": "NOT_FOUND"}
SELF_DECISION = {"code": "SELF_DECISION_NOT_ALLOWED"}


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


async def submitted_request(client: AsyncClient, organiser: User) -> uuid.UUID:
    """A request submitted through the API, so it has its reference like a real one."""
    draft = (await client.post("/api/v1/event-requests", headers=auth(organiser), json=complete_request())).json()
    submitted = await client.post(f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser))
    assert submitted.status_code == 200
    return uuid.UUID(draft["id"])


def assign(db: Session, request_id: uuid.UUID, coordinator: User | None) -> Event:
    """Sets the coordinator directly, as a Lead's assignment (or, until SCRUM-83, a reassignment) would."""
    event = db.get(Event, request_id)
    event.coordinator_id = coordinator.id if coordinator else None
    db.flush()
    return event


def stored_clarifications(db: Session, request_id: uuid.UUID) -> list[EventRequestClarification]:
    return list(db.scalars(select(EventRequestClarification).where(EventRequestClarification.event_id == request_id)))


# --- TC-US16B-09 the coordinator's review queue (AC 5, D48) ---


async def test_tc_us16b_09_a_coordinator_sees_only_requests_assigned_to_them(client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    coordinator_a = make_user(db, UserRole.COORDINATOR)
    coordinator_b = make_user(db, UserRole.COORDINATOR)
    venue_staff = make_user(db, UserRole.VENUE_STAFF)
    multi_role = make_user(db, UserRole.COORDINATOR, UserRole.VENUE_STAFF)
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    for_a = await submitted_request(client, organiser)
    for_b = await submitted_request(client, organiser)
    unassigned = await submitted_request(client, organiser)
    assign(db, for_a, coordinator_a)
    assign(db, for_b, coordinator_b)

    def ids(response) -> set[str]:
        return {row["id"] for row in response.json()["event_requests"]}

    as_a = await client.get("/api/v1/event-requests", headers=auth(coordinator_a))
    as_venue_staff = await client.get("/api/v1/event-requests", headers=auth(venue_staff))
    as_multi_role = await client.get("/api/v1/event-requests", headers=auth(multi_role))
    as_lead = await client.get("/api/v1/event-requests", headers=auth(lead))

    assert ids(as_a) == {str(for_a)}
    assert (as_venue_staff.status_code, as_venue_staff.json()) == (403, FORBIDDEN)
    assert ids(as_multi_role) == set()
    # Leads keep the whole queue (D11): they assign from it.
    assert {str(for_a), str(for_b), str(unassigned)} <= ids(as_lead)


# --- TC-US16B-10 a request's details and thread (AC 5, D48) ---


async def test_tc_us16b_10_only_the_assigned_coordinator_opens_a_request_and_its_thread(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    coordinator_a = make_user(db, UserRole.COORDINATOR)
    coordinator_b = make_user(db, UserRole.COORDINATOR)
    venue_staff = make_user(db, UserRole.VENUE_STAFF)
    request_id = await submitted_request(client, organiser)
    assign(db, request_id, coordinator_a)
    paths = (f"/api/v1/event-requests/{request_id}", f"/api/v1/event-requests/{request_id}/clarifications")

    for path in paths:
        as_b = await client.get(path, headers=auth(coordinator_b))
        as_venue_staff = await client.get(path, headers=auth(venue_staff))
        as_a = await client.get(path, headers=auth(coordinator_a))

        # Another coordinator holds the role, so the request just doesn't exist for them; Venue Staff
        # don't hold a role that reads requests at all (AC 3).
        assert (as_b.status_code, as_b.json()) == (404, NOT_FOUND), path
        assert (as_venue_staff.status_code, as_venue_staff.json()) == (403, FORBIDDEN), path
        assert as_a.status_code == 200, path


# --- TC-US16B-11 sending a clarification (AC 5, D14 retired) ---


async def test_tc_us16b_11_only_the_assigned_coordinator_asks_for_clarification(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    coordinator_a = make_user(db, UserRole.COORDINATOR)
    coordinator_b = make_user(db, UserRole.COORDINATOR)
    for_a = await submitted_request(client, organiser)
    unassigned = await submitted_request(client, organiser)
    assign(db, for_a, coordinator_a)

    by_b = await client.post(f"/api/v1/event-requests/{for_a}/clarifications", headers=auth(coordinator_b), json=QUESTION)
    on_unassigned = [
        await client.post(f"/api/v1/event-requests/{unassigned}/clarifications", headers=auth(coordinator), json=QUESTION)
        for coordinator in (coordinator_a, coordinator_b)
    ]

    assert (by_b.status_code, by_b.json()) == (404, NOT_FOUND)
    assert [(response.status_code, response.json()) for response in on_unassigned] == [(404, NOT_FOUND)] * 2
    assert stored_clarifications(db, for_a) == [] and stored_clarifications(db, unassigned) == []
    assert notifier.clarifications == []

    by_a = await client.post(f"/api/v1/event-requests/{for_a}/clarifications", headers=auth(coordinator_a), json=QUESTION)

    assert by_a.status_code == 201
    assert len(stored_clarifications(db, for_a)) == 1


# --- TC-US16B-12 another organiser's request (AC 4, D47) ---


async def test_tc_us16b_12_another_organisers_request_behaves_as_if_it_doesnt_exist(
    client: AsyncClient, db: Session
) -> None:
    organiser_a = make_user(db, UserRole.ORGANISER)
    organiser_b = make_user(db, UserRole.ORGANISER)
    coordinator = make_user(db, UserRole.COORDINATOR)
    draft = (await client.post("/api/v1/event-requests", headers=auth(organiser_a), json=complete_request())).json()
    asked = await submitted_request(client, organiser_a)
    assign(db, asked, coordinator)
    question = await client.post(f"/api/v1/event-requests/{asked}/clarifications", headers=auth(coordinator), json=QUESTION)
    assert question.status_code == 201

    attempts = [
        await client.get(f"/api/v1/event-requests/{asked}", headers=auth(organiser_b)),
        await client.get(f"/api/v1/event-requests/{asked}/clarifications", headers=auth(organiser_b)),
        await client.patch(f"/api/v1/event-requests/{draft['id']}", headers=auth(organiser_b), json={"name": "Mine now"}),
        await client.post(f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser_b)),
        await client.post(
            f"/api/v1/event-requests/{asked}/clarifications/response",
            headers=auth(organiser_b),
            json={"comment": "Forty."},
        ),
    ]

    assert [(response.status_code, response.json()) for response in attempts] == [(404, NOT_FOUND)] * 5
    assert db.get(Event, uuid.UUID(draft["id"])).name == complete_request()["name"]
    assert len(stored_clarifications(db, asked)) == 1


# --- TC-US16B-13 attendees reach nothing internal (AC 6) ---


def keys(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys(item)


async def test_tc_us16b_13_an_attendee_is_refused_every_internal_route(client: AsyncClient, db: Session) -> None:
    attendee = make_attendee(db)
    user = db.get(User, attendee.id)
    organiser = make_user(db, UserRole.ORGANISER)
    request_id = await submitted_request(client, organiser)
    event = make_event(db)
    make_registration(db, event, attendee)
    internal = [
        ("GET", "/api/v1/event-requests"),
        ("GET", f"/api/v1/event-requests/{request_id}"),
        ("GET", f"/api/v1/event-requests/{request_id}/clarifications"),
        ("POST", f"/api/v1/event-requests/{request_id}/clarifications"),
        ("GET", f"/api/v1/event-requests/{request_id}/assignment-history"),
        ("GET", "/api/v1/venue-bookings/pending"),
        ("POST", "/api/v1/venue-bookings"),
        ("GET", f"/api/v1/events/{event.id}/venue-bookings"),
        ("GET", "/api/v1/equipment-lines"),
        ("GET", f"/api/v1/events/{event.id}/equipment-lines"),
        ("GET", "/api/v1/venues/available"),
    ]

    for method, path in internal:
        response = await client.request(method, path, headers=auth(user), json={} if method == "POST" else None)
        assert (response.status_code, response.json()) == (403, FORBIDDEN), path

    board = await client.get("/api/v1/events/available", headers={"X-Attendee-Id": str(attendee.id)})
    mine = await client.get("/api/v1/me/registrations", headers={"X-Attendee-Id": str(attendee.id)})
    assert (board.status_code, mine.status_code) == (200, 200)
    seen = set(keys(board.json())) | set(keys(mine.json()))
    assert not {key for key in seen if any(word in key for word in ("clarification", "booking", "equipment"))}


# --- TC-US16B-14 every role-gated route refuses the roles it doesn't name (AC 3) ---

ROLES = list(UserRole)
ORGANISER, COORDINATOR, LEAD = UserRole.ORGANISER, UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD
VENUE_STAFF, TECH_SUPPORT = UserRole.VENUE_STAFF, UserRole.TECH_SUPPORT
ID = uuid.uuid4()
# One row per role-gated route: who may call it. Ids are unknown, so an allowed role gets past the role
# check to a 404 or 422; the others are stopped at it.
ROUTES = [
    ("POST", "/api/v1/event-requests", {ORGANISER}),
    ("GET", "/api/v1/me/event-requests", {ORGANISER}),
    ("GET", "/api/v1/event-requests", {COORDINATOR, LEAD}),
    ("GET", f"/api/v1/event-requests/{ID}", {ORGANISER, COORDINATOR, LEAD}),
    ("PATCH", f"/api/v1/event-requests/{ID}", {ORGANISER}),
    ("POST", f"/api/v1/event-requests/{ID}/submit", {ORGANISER}),
    ("GET", "/api/v1/event-requests/unassigned", {LEAD}),
    ("GET", "/api/v1/event-requests/assigned", {LEAD}),
    ("GET", "/api/v1/coordinators", {LEAD}),
    ("POST", f"/api/v1/event-requests/{ID}/assignment", {LEAD}),
    ("GET", f"/api/v1/event-requests/{ID}/assignment-history", {LEAD}),
    ("POST", f"/api/v1/event-requests/{ID}/clarifications", {COORDINATOR}),
    ("GET", f"/api/v1/event-requests/{ID}/clarifications", {ORGANISER, COORDINATOR, LEAD}),
    ("POST", f"/api/v1/event-requests/{ID}/clarifications/response", {ORGANISER}),
    ("GET", "/api/v1/venues/available", {COORDINATOR, VENUE_STAFF}),
    ("POST", "/api/v1/venues", {VENUE_STAFF}),
    ("PATCH", f"/api/v1/venues/{ID}", {VENUE_STAFF}),
    ("POST", f"/api/v1/venues/{ID}/deactivate", {VENUE_STAFF}),
    ("POST", f"/api/v1/venues/{ID}/reactivate", {VENUE_STAFF}),
    ("POST", "/api/v1/venue-bookings", {COORDINATOR}),
    ("POST", f"/api/v1/venue-bookings/{ID}/withdraw", {COORDINATOR}),
    ("GET", "/api/v1/venue-bookings/pending", {VENUE_STAFF}),
    ("GET", f"/api/v1/venue-bookings/{ID}/evaluation", {VENUE_STAFF}),
    ("POST", f"/api/v1/venue-bookings/{ID}/approve", {VENUE_STAFF}),
    ("POST", f"/api/v1/venue-bookings/{ID}/reject", {VENUE_STAFF}),
    ("GET", f"/api/v1/events/{ID}/venue-bookings", {COORDINATOR, VENUE_STAFF}),
    ("GET", "/api/v1/me/equipment-events", {COORDINATOR}),
    ("GET", f"/api/v1/events/{ID}/equipment-lines", {COORDINATOR}),
    ("POST", f"/api/v1/events/{ID}/equipment-lines", {COORDINATOR}),
    ("PATCH", f"/api/v1/equipment-lines/{ID}", {COORDINATOR}),
    ("DELETE", f"/api/v1/equipment-lines/{ID}", {COORDINATOR}),
    ("GET", "/api/v1/equipment-lines", {TECH_SUPPORT}),
    ("POST", f"/api/v1/equipment-lines/{ID}/review", {TECH_SUPPORT}),
]


@pytest.mark.parametrize(("method", "path", "allowed"), ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
async def test_tc_us16b_14_each_route_allows_only_the_roles_it_names(
    client: AsyncClient, db: Session, method: str, path: str, allowed: set[UserRole]
) -> None:
    body = {} if method in ("POST", "PATCH") else None

    anonymous = await client.request(method, path, json=body)
    assert (anonymous.status_code, anonymous.json()) == (401, {"code": "UNAUTHENTICATED"})

    for role in ROLES:
        response = await client.request(method, path, headers=auth(make_user(db, role)), json=body)
        if role in allowed:
            assert response.status_code not in (401, 403), role
        else:
            assert (response.status_code, response.json()) == (403, FORBIDDEN), role


# --- TC-US16B-15 Leads (AC 7) ---


async def test_tc_us16b_15_each_lead_sees_only_the_requests_they_assigned(client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    coordinator = make_user(db, UserRole.COORDINATOR)
    lead_one = make_user(db, UserRole.COORDINATOR_LEAD)
    lead_two = make_user(db, UserRole.COORDINATOR_LEAD)
    first = await submitted_request(client, organiser)
    second = await submitted_request(client, organiser)
    for lead, request_id in ((lead_one, first), (lead_two, second)):
        assigned = await client.post(
            f"/api/v1/event-requests/{request_id}/assignment",
            headers=auth(lead),
            json={"coordinator_id": str(coordinator.id)},
        )
        assert assigned.status_code == 200

    for lead, request_id in ((lead_one, first), (lead_two, second)):
        rows = (await client.get("/api/v1/event-requests/assigned", headers=auth(lead))).json()["event_requests"]
        assert [row["id"] for row in rows] == [str(request_id)]


def test_tc_us16b_15_no_route_creates_users_or_changes_roles() -> None:
    """The Lead role carries no account administration (AC 7): no route manages users or roles. Sign-up's
    `POST /auth/profile` creates only the caller's own Organiser or Attendee profile (US16a)."""
    paths = app.openapi()["paths"]

    assert [path for path in paths if "/users" in path or "/roles" in path] == []
    creates = {path for path, operations in paths.items() if "post" in operations and "profile" in path}
    assert creates == {"/api/v1/auth/profile"}


# --- TC-US16B-25 no one decides a booking or line they're tied to (D51) ---


async def test_tc_us16b_25_venue_staff_cant_decide_a_booking_they_made_or_whose_event_they_coordinate(
    client: AsyncClient, db: Session
) -> None:
    multi_role = make_user(db, UserRole.COORDINATOR, UserRole.VENUE_STAFF)
    previous = make_user(db, UserRole.COORDINATOR)
    independent = make_user(db, UserRole.VENUE_STAFF)
    venue = make_venue(db, name="Hall A")
    theirs = make_event(db, name="Their event", status=EventStatus.APPROVED, coordinator_id=multi_role.id)
    handed_over = make_event(db, name="Handed over", status=EventStatus.APPROVED, coordinator_id=previous.id)
    own_booking = make_venue_booking(db, event=theirs, venue=venue, user=multi_role)
    inherited = make_venue_booking(db, event=handed_over, venue=venue, user=previous, starts_at=NOW + timedelta(days=14))
    # The event is now multi_role's, though the previous coordinator made the request.
    assign(db, handed_over.id, multi_role)

    attempts = [
        await client.post(f"/api/v1/venue-bookings/{booking.id}/{decision}", headers=auth(multi_role), json={})
        for booking in (own_booking, inherited)
        for decision in ("approve", "reject")
    ]

    assert [(response.status_code, response.json()) for response in attempts] == [(403, SELF_DECISION)] * 4
    for booking in (own_booking, inherited):
        db.refresh(booking)
        assert (booking.status, booking.decided_by_user_id) == (VenueBookingStatus.REQUESTED, None)
    decided = await client.post(f"/api/v1/venue-bookings/{inherited.id}/approve", headers=auth(independent), json={})
    assert decided.status_code == 200


async def test_tc_us16b_25_tech_support_cant_review_a_line_they_made_or_whose_event_they_coordinate(
    client: AsyncClient, db: Session
) -> None:
    both = make_user(db, UserRole.COORDINATOR, UserRole.TECH_SUPPORT)
    previous = make_user(db, UserRole.COORDINATOR)
    independent = make_user(db, UserRole.TECH_SUPPORT)
    theirs = make_event(db, name="Their event", status=EventStatus.CONFIRMED, coordinator_id=both.id)
    handed_over = make_event(db, name="Handed over", status=EventStatus.CONFIRMED, coordinator_id=previous.id)
    own_line = make_line(db, event=theirs, equipment_type=make_type(db), requested_by=both)
    inherited = make_line(db, event=handed_over, equipment_type=make_type(db), requested_by=previous)
    assign(db, handed_over.id, both)

    attempts = [
        await client.post(f"/api/v1/equipment-lines/{line.id}/review", headers=auth(both), json={"decision": decision})
        for line in (own_line, inherited)
        for decision in ("approved", "rejected")
    ]

    assert [(response.status_code, response.json()) for response in attempts] == [(403, SELF_DECISION)] * 4
    for line in (own_line, inherited):
        db.refresh(line)
        assert (line.status, line.reviewed_by_user_id) == (EquipmentLineStatus.PENDING, None)
    reviewed = await client.post(
        f"/api/v1/equipment-lines/{inherited.id}/review", headers=auth(independent), json={"decision": "approved"}
    )
    assert reviewed.status_code == 200


# --- TC-US16B-26 the thread follows a reassignment (D48) ---


async def test_tc_us16b_26_the_new_coordinator_takes_over_the_thread(client: AsyncClient, db: Session) -> None:
    organiser = make_user(db, UserRole.ORGANISER)
    coordinator_a = make_user(db, UserRole.COORDINATOR)
    coordinator_b = make_user(db, UserRole.COORDINATOR)
    request_id = await submitted_request(client, organiser)
    assign(db, request_id, coordinator_a)
    thread = f"/api/v1/event-requests/{request_id}/clarifications"
    assert (await client.post(thread, headers=auth(coordinator_a), json=QUESTION)).status_code == 201

    # Until SCRUM-83 builds reassigning, the assignment is changed directly.
    assign(db, request_id, coordinator_b)

    as_b = await client.get(thread, headers=auth(coordinator_b))
    as_a = [await client.get(path, headers=auth(coordinator_a)) for path in (thread, f"/api/v1/event-requests/{request_id}")]
    assert as_b.status_code == 200
    assert [message["comment"] for message in as_b.json()["clarifications"]] == [QUESTION["comment"]]
    assert [(response.status_code, response.json()) for response in as_a] == [(404, NOT_FOUND)] * 2

    answered = await client.post(f"{thread}/response", headers=auth(organiser), json={"comment": "About forty."})
    assert answered.status_code == 201
    follow_up = await client.post(thread, headers=auth(coordinator_b), json=QUESTION)
    assert follow_up.status_code == 201
    assert len(stored_clarifications(db, request_id)) == 3


# --- TC-US16B-28 assignment (D51) ---


async def test_tc_us16b_28_a_lead_cant_assign_a_request_they_created(client: AsyncClient, db: Session) -> None:
    lead_and_organiser = make_user(db, UserRole.ORGANISER, UserRole.COORDINATOR_LEAD)
    coordinator = make_user(db, UserRole.COORDINATOR)
    request_id = await submitted_request(client, lead_and_organiser)

    response = await client.post(
        f"/api/v1/event-requests/{request_id}/assignment",
        headers=auth(lead_and_organiser),
        json={"coordinator_id": str(coordinator.id)},
    )

    assert (response.status_code, response.json()) == (403, SELF_DECISION)
    event = db.get(Event, request_id)
    db.refresh(event)
    assert (event.coordinator_id, event.status) == (None, EventStatus.SUBMITTED)


async def test_tc_us16b_28_a_request_cant_be_assigned_to_its_creator(client: AsyncClient, db: Session) -> None:
    coordinator_and_organiser = make_user(db, UserRole.ORGANISER, UserRole.COORDINATOR)
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    request_id = await submitted_request(client, coordinator_and_organiser)

    response = await client.post(
        f"/api/v1/event-requests/{request_id}/assignment",
        headers=auth(lead),
        json={"coordinator_id": str(coordinator_and_organiser.id)},
    )

    assert (response.status_code, response.json()) == (
        422,
        {"code": "INVALID_COORDINATOR", "reason": "created_the_request"},
    )
    event = db.get(Event, request_id)
    db.refresh(event)
    assert (event.coordinator_id, event.status) == (None, EventStatus.SUBMITTED)


# --- TC-US16B-29 the database refuses a self-decision too (D51) ---


def test_tc_us16b_29_a_booking_cant_be_decided_by_its_requester(db: Session) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR, UserRole.VENUE_STAFF)
    event = make_event(db, status=EventStatus.APPROVED, coordinator_id=coordinator.id)

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_venue_booking(
                db,
                event=event,
                venue=make_venue(db),
                user=coordinator,
                status=VenueBookingStatus.APPROVED,
                decided_by_user_id=coordinator.id,
            )

    assert raised.value.orig.diag.constraint_name == "venue_bookings_decider_not_requester"


def test_tc_us16b_29_a_line_cant_be_reviewed_by_its_requester(db: Session) -> None:
    coordinator = make_user(db, UserRole.COORDINATOR, UserRole.TECH_SUPPORT)
    event = make_event(db, coordinator_id=coordinator.id)

    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            make_line(
                db,
                event=event,
                equipment_type=make_type(db),
                requested_by=coordinator,
                status=EquipmentLineStatus.APPROVED,
                reviewer=coordinator,
            )

    assert raised.value.orig.diag.constraint_name == "equipment_request_lines_reviewer_not_requester"


def test_tc_us16b_29_the_seed_still_runs_and_there_is_one_head(db: Session) -> None:
    seed(db, now=NOW)

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == [REVISION]
