"""US30a (SCRUM-99): the Safety Officer reviews an event's arrangements, and the coordinator and organiser
see the outcome. US30b (SCRUM-100): or asks for changes, which the coordinator marks done."""

import logging
import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.equipment.models import EquipmentLineStatus
from app.event.models import DeliveryMode, Event, EventStatus
from app.main import app
from app.safety.models import CHECKLIST_KEYS, SafetyReview
from app.user.models import User, UserRole
from app.venue.models import Venue, VenueBookingStatus
from tests.conftest import FakeNotifier
from tests.equipment.test_equipment_api import make_line
from tests.equipment.test_equipment_schema import make_type
from tests.event.test_confirmation import book, reserve
from tests.event.test_event_request_clarification_api import make_request
from tests.event.test_event_requests import auth
from tests.factories import NOW, make_user, make_venue

pytestmark = pytest.mark.anyio

STARTS = NOW + timedelta(days=7)
QUEUE = "/api/v1/safety-reviews"


def ok(**overrides: dict) -> dict:
    """A checklist with every item satisfactory, with any item replaced."""
    checklist: dict = {key: {"result": "satisfactory"} for key in CHECKLIST_KEYS}
    return checklist | overrides


def approval(**overrides: object) -> dict:
    return {"outcome": "approved", "checklist": ok(), "comments": "All clear.", "internal_notes": "Checked the plan."} | overrides


def rejection(**overrides: object) -> dict:
    return {
        "outcome": "rejected",
        "checklist": ok(emergency_access={"result": "issue", "comment": "Only one exit is clear."}),
        "comments": "Keep the side door clear and add a second exit.",
        "internal_notes": "Venue has history of blocked exits.",
    } | overrides


async def review(client: AsyncClient, officer: User | None, event: Event, body: dict | None = None):
    return await client.post(f"{QUEUE}/{event.id}", headers=auth(officer) if officer else {}, json=approval() if body is None else body)


async def queue(client: AsyncClient, officer: User) -> list[dict]:
    response = await client.get(QUEUE, headers=auth(officer))
    assert response.status_code == 200
    return response.json()["events"]


@pytest.fixture
def organiser(db: Session) -> User:
    user = make_user(db, UserRole.ORGANISER)
    user.email = "olivia.organiser@smu.edu.sg"
    db.flush()
    return user


@pytest.fixture
def casey(db: Session) -> User:
    user = make_user(db, UserRole.COORDINATOR)
    user.email = "casey.tan@smu.edu.sg"
    user.full_name = "Casey Tan"
    db.flush()
    return user


@pytest.fixture
def officer(db: Session) -> User:
    user = make_user(db, UserRole.SAFETY_OFFICER)
    user.full_name = "Sam Safety"
    db.flush()
    return user


@pytest.fixture
def venue_staff(db: Session) -> User:
    return make_user(db, UserRole.VENUE_STAFF)


@pytest.fixture
def venue(db: Session) -> Venue:
    return make_venue(db, name="SCIS Seminar Room 2-1")


@pytest.fixture
def event(db: Session, organiser: User, casey: User, venue: Venue, venue_staff: User) -> Event:
    """An approved event Casey coordinates, its venue booking approved, nothing pending: in the queue."""
    request = make_request(db, organiser, EventStatus.APPROVED, coordinator=casey)
    request.request_reference = "ER-2026-000099"
    request.expected_attendees = 35
    request.accessibility_needs = "Step-free access"
    request.submitted_at = NOW - timedelta(days=2)
    db.flush()
    book(db, request, venue, casey, venue_staff, starts_at=STARTS)
    return request


def reviews(db: Session, event: Event) -> list[SafetyReview]:
    return list(db.scalars(select(SafetyReview).where(SafetyReview.event_id == event.id).order_by(SafetyReview.created_at)))


# --- AC 1: the queue ---


async def test_tc_us30a_01_the_queue_lists_an_event_whose_arrangements_are_approved(
    client: AsyncClient, event: Event, officer: User
) -> None:
    [row] = await queue(client, officer)

    assert datetime.fromisoformat(row.pop("starts_at")) == STARTS
    assert row == {
        "event_id": str(event.id),
        "name": "Community design workshop",
        "request_reference": "ER-2026-000099",
        "expected_attendees": 35,
        "venues": ["SCIS Seminar Room 2-1"],
        "resent": False,
    }


async def test_tc_us30a_02_the_queue_leaves_out_what_is_not_ready_or_already_decided(
    client: AsyncClient, db: Session, organiser: User, casey: User, venue: Venue, venue_staff: User, officer: User, event: Event
) -> None:
    pending_booking = make_request(db, organiser, EventStatus.APPROVED, coordinator=casey)
    book(db, pending_booking, make_venue(db), casey, venue_staff, status=VenueBookingStatus.REQUESTED, starts_at=STARTS)
    no_venue = make_request(db, organiser, EventStatus.APPROVED, coordinator=casey)
    pending_equipment = make_request(db, organiser, EventStatus.APPROVED, coordinator=casey)
    book(db, pending_equipment, make_venue(db), casey, venue_staff, starts_at=STARTS + timedelta(days=1))
    make_line(db, event=pending_equipment, equipment_type=make_type(db), requested_by=casey)
    approved = make_request(db, organiser, EventStatus.APPROVED, coordinator=casey)
    book(db, approved, make_venue(db), casey, venue_staff, starts_at=STARTS + timedelta(days=2))
    approved.safety_approved_at, approved.safety_approved_by_user_id = NOW, officer.id
    under_review = make_request(db, organiser, EventStatus.UNDER_REVIEW, coordinator=casey)
    book(db, under_review, make_venue(db), casey, venue_staff, starts_at=STARTS + timedelta(days=3))
    db.flush()

    assert [row["event_id"] for row in await queue(client, officer)] == [str(event.id)]
    assert no_venue.id not in [row["event_id"] for row in await queue(client, officer)]


async def test_tc_us30a_03_requested_equipment_must_be_reserved_before_an_event_is_queued(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    line = make_line(db, event=event, equipment_type=make_type(db), requested_by=casey, status=EquipmentLineStatus.APPROVED)

    assert await queue(client, officer) == []  # approved, but not reserved yet (US27)

    reserve(db, line, line.reviewed_by_user_id and db.get(User, line.reviewed_by_user_id))
    assert [row["event_id"] for row in await queue(client, officer)] == [str(event.id)]
    # Technical support is the coordinator's to arrange for confirming; it doesn't hold up the review.
    assert (await review(client, officer, event)).status_code == 201


async def test_tc_us30a_04_a_planning_event_is_in_the_queue_too(
    client: AsyncClient, db: Session, event: Event, officer: User
) -> None:
    event.status = EventStatus.PLANNING
    event.start_at, event.end_at, event.capacity, event.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    assert [row["event_id"] for row in await queue(client, officer)] == [str(event.id)]


async def test_tc_us30a_49_an_online_event_with_no_booking_is_queued_without_breaking_the_queue(
    client: AsyncClient, db: Session, organiser: User, casey: User, event: Event, officer: User
) -> None:
    online = make_request(db, organiser, EventStatus.APPROVED, coordinator=casey)
    online.delivery_mode = DeliveryMode.ONLINE
    online.expected_attendees = 20
    db.flush()

    rows = {row["event_id"]: row for row in await queue(client, officer)}

    assert set(rows) == {str(event.id), str(online.id)}
    assert (rows[str(online.id)]["venues"], rows[str(online.id)]["starts_at"]) == ([], None)
    assert datetime.fromisoformat(rows[str(event.id)]["starts_at"]) == STARTS


# --- AC 2, 9: what the Safety Officer opens ---


async def test_tc_us30a_05_the_review_shows_only_what_a_safety_review_needs(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    line = make_line(db, event=event, equipment_type=make_type(db, "Projector"), requested_by=casey, status=EquipmentLineStatus.APPROVED, quantity=2)
    reserve(db, line, db.get(User, line.reviewed_by_user_id))

    response = await client.get(f"{QUEUE}/{event.id}", headers=auth(officer))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"event", "state", "venues", "equipment", "checklist", "change_areas", "history"}
    assert [area["key"] for area in body["change_areas"]] == ["venue", "layout", "equipment", "accessibility", "other"]
    assert set(body["event"]) == {
        "id", "name", "request_reference", "status", "expected_attendees",
        "room_layout_preference", "accessibility_needs", "equipment_needs",
    }
    assert body["event"]["accessibility_needs"] == "Step-free access"
    assert [(v["venue_name"], v["venue_capacity"], v["room_layout"]) for v in body["venues"]] == [("SCIS Seminar Room 2-1", 40, "theatre")]
    assert [(e["equipment_type"], e["quantity"]) for e in body["equipment"]] == [("Projector", 2)]
    assert [item["key"] for item in body["checklist"]] == list(CHECKLIST_KEYS)
    assert body["state"] == "pending" and body["history"] == []


async def test_tc_us30a_06_an_event_nobody_has_reviewed_and_that_is_not_in_the_queue_is_not_opened(
    client: AsyncClient, db: Session, organiser: User, casey: User, officer: User
) -> None:
    unready = make_request(db, organiser, EventStatus.APPROVED, coordinator=casey)
    draft = make_request(db, organiser, EventStatus.DRAFT)

    for target in (unready.id, draft.id, uuid.uuid4()):
        assert (await client.get(f"{QUEUE}/{target}", headers=auth(officer))).status_code == 404


# --- AC 3, 6: approve ---


async def test_tc_us30a_07_approving_records_the_review_and_lets_the_event_be_confirmed(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    response = await review(client, officer, event)

    assert response.status_code == 201
    body = response.json()
    assert (body["outcome"], body["comments"], body["internal_notes"]) == ("approved", "All clear.", "Checked the plan.")
    assert body["reviewer"] == {"id": str(officer.id), "name": "Sam Safety"}
    [stored] = reviews(db, event)
    assert (stored.reviewer_id, stored.outcome, stored.created_at) == (officer.id, "approved", NOW)
    assert set(stored.checklist) == set(CHECKLIST_KEYS)
    db.refresh(event)
    assert (event.safety_approved_at, event.safety_approved_by_user_id, event.status) == (NOW, officer.id, EventStatus.APPROVED)
    # US18: the safety item is now complete, so the coordinator can confirm.
    assert (await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(casey))).status_code == 200


async def test_tc_us30a_08_an_approval_with_a_flagged_item_is_refused(
    client: AsyncClient, db: Session, event: Event, officer: User
) -> None:
    flagged = ok(layout={"result": "issue", "comment": "Aisles too narrow"})

    response = await review(client, officer, event, approval(checklist=flagged))

    assert response.status_code == 422
    assert response.json() == {"code": "CHECKLIST_HAS_ISSUES", "fields": ["checklist.layout"]}
    assert reviews(db, event) == []


# --- AC 4: reject ---


async def test_tc_us30a_09_a_rejection_keeps_the_event_in_its_status_with_the_reason_for_the_coordinator(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    response = await review(client, officer, event, rejection())

    assert response.status_code == 201
    db.refresh(event)
    assert (event.status, event.safety_approved_at) == (EventStatus.APPROVED, None)  # the event isn't rejected
    readiness = (await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(casey))).json()
    safety = next(item for item in readiness["items"] if item["kind"] == "safety")
    assert safety["complete"] is False
    assert "Keep the side door clear and add a second exit." in safety["detail"]
    # A rejected arrangement can't be confirmed (US18).
    assert (await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(casey))).status_code == 409


@pytest.mark.parametrize("comments", [None, "", "   "])
async def test_tc_us30a_10_a_rejection_needs_comments(
    client: AsyncClient, db: Session, event: Event, officer: User, comments: str | None
) -> None:
    response = await review(client, officer, event, rejection(comments=comments))

    assert response.status_code == 422
    assert response.json() == {"code": "MISSING_REQUIRED_FIELD", "fields": ["comments"]}
    assert reviews(db, event) == []


async def test_tc_us30a_11_a_missing_outcome_or_checklist_item_is_named(
    client: AsyncClient, db: Session, event: Event, officer: User
) -> None:
    partial = {key: value for key, value in ok().items() if key not in ("layout", "crowd_movement")}

    response = await review(client, officer, event, {"checklist": partial})

    assert response.status_code == 422
    assert response.json() == {
        "code": "MISSING_REQUIRED_FIELD",
        "fields": ["outcome", "checklist.layout", "checklist.crowd_movement"],
    }
    assert (await review(client, officer, event, {"outcome": "approved"})).json()["fields"][0] == "checklist.attendance_capacity"
    assert reviews(db, event) == []


async def test_tc_us30a_12_an_unknown_checklist_item_is_refused(client: AsyncClient, event: Event, officer: User) -> None:
    response = await review(client, officer, event, approval(checklist=ok(parking={"result": "satisfactory"})))

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_SAFETY_REVIEW"


async def test_tc_us30a_13_the_database_refuses_a_rejection_without_comments_and_an_unknown_outcome(
    db: Session, event: Event, officer: User
) -> None:
    for outcome, comments, name in (
        ("rejected", None, "safety_reviews_rejection_has_comments"),
        ("rejected", "  ", "safety_reviews_rejection_has_comments"),
        ("maybe", "x", "safety_reviews_outcome_known"),
    ):
        with pytest.raises(IntegrityError) as raised:
            with db.begin_nested():
                db.add(SafetyReview(event_id=event.id, reviewer_id=officer.id, outcome=outcome, checklist={}, comments=comments))
                db.flush()
        assert raised.value.orig.diag.constraint_name == name


# --- when a review is allowed ---


@pytest.mark.parametrize(
    "status", [EventStatus.UNDER_REVIEW, EventStatus.CONFIRMED, EventStatus.PREPARATION, EventStatus.CANCELLED, EventStatus.REJECTED]
)
async def test_tc_us30a_14_only_an_approved_or_planning_event_is_reviewed(
    client: AsyncClient, db: Session, event: Event, officer: User, status: EventStatus
) -> None:
    event.status = status
    event.start_at, event.end_at, event.capacity, event.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    response = await review(client, officer, event)

    assert (response.status_code, response.json()["reason"]) == (409, "status")
    assert reviews(db, event) == []


async def test_tc_us30a_15_an_event_with_an_arrangement_outstanding_is_not_reviewed(
    client: AsyncClient, db: Session, event: Event, casey: User, venue_staff: User, officer: User
) -> None:
    book(db, event, make_venue(db), casey, venue_staff, status=VenueBookingStatus.REQUESTED, starts_at=STARTS + timedelta(days=2))

    response = await review(client, officer, event)

    assert (response.status_code, response.json()["reason"]) == (409, "arrangements_incomplete")


async def test_tc_us30a_16_a_decided_event_is_not_reviewed_again(
    client: AsyncClient, event: Event, officer: User
) -> None:
    assert (await review(client, officer, event)).status_code == 201

    second = await review(client, officer, event)

    assert (second.status_code, second.json()["reason"]) == (409, "already_approved")


async def test_tc_us30a_17_a_rejected_event_waits_for_the_coordinator_to_send_it_back(
    client: AsyncClient, event: Event, officer: User
) -> None:
    await review(client, officer, event, rejection())

    again = await review(client, officer, event)

    assert (again.status_code, again.json()["reason"]) == (409, "awaiting_revision")
    assert await queue(client, officer) == []


async def test_tc_us30a_18_a_draft_or_unknown_event_is_404(client: AsyncClient, db: Session, organiser: User, officer: User) -> None:
    draft = make_request(db, organiser, EventStatus.DRAFT)

    assert (await review(client, officer, draft)).status_code == 404
    assert (await client.post(f"{QUEUE}/{uuid.uuid4()}", headers=auth(officer), json=approval())).status_code == 404


# --- AC 4: revise and send it for another review ---


async def test_tc_us30a_19_the_coordinator_sends_a_rejected_arrangement_back_and_it_rejoins_the_queue(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    await review(client, officer, event, rejection())

    sent = await client.post(f"/api/v1/event-requests/{event.id}/safety-review-request", headers=auth(casey))

    assert sent.status_code == 200
    assert sent.json()["state"] == "pending"
    [row] = await queue(client, officer)
    assert (row["event_id"], row["resent"]) == (str(event.id), True)
    readiness = (await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(casey))).json()
    assert next(i for i in readiness["items"] if i["kind"] == "safety")["detail"] == "Sent for another safety review."


async def test_tc_us30a_20_sending_back_is_refused_when_there_is_nothing_to_send(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    url = f"/api/v1/event-requests/{event.id}/safety-review-request"

    never = await client.post(url, headers=auth(casey))
    await review(client, officer, event, rejection())
    first = await client.post(url, headers=auth(casey))
    twice = await client.post(url, headers=auth(casey))
    await review(client, officer, event)
    approved = await client.post(url, headers=auth(casey))

    assert [(r.status_code, r.json()["reason"]) for r in (never, twice, approved)] == [
        (409, "not_rejected"),
        (409, "already_requested"),
        (409, "already_approved"),
    ]
    assert first.status_code == 200


async def test_tc_us30a_21_only_the_events_coordinator_sends_it_back(
    client: AsyncClient, db: Session, event: Event, officer: User, organiser: User
) -> None:
    await review(client, officer, event, rejection())
    other = make_user(db, UserRole.COORDINATOR)
    url = f"/api/v1/event-requests/{event.id}/safety-review-request"

    assert (await client.post(url, headers=auth(other))).status_code == 404
    assert (await client.post(url, headers=auth(organiser))).status_code == 403
    assert (await client.post(url, headers=auth(officer))).status_code == 403
    assert (await client.post(url)).status_code == 401


async def test_tc_us30a_22_reject_resubmit_approve_then_confirm(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    await review(client, officer, event, rejection())
    await client.post(f"/api/v1/event-requests/{event.id}/safety-review-request", headers=auth(casey))

    assert (await review(client, officer, event, approval())).status_code == 201
    assert (await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(casey))).status_code == 200


# --- AC 6: each review recorded ---


async def test_tc_us30a_23_every_review_is_kept_with_reviewer_outcome_comments_and_time(
    client: AsyncClient, db: Session, event: Event, officer: User
) -> None:
    other = make_user(db, UserRole.SAFETY_OFFICER)
    first = await review(client, officer, event, rejection())
    # Move the first review back a minute so the order is visible (the test clock is fixed).
    stored = reviews(db, event)[0]
    stored.created_at = NOW - timedelta(minutes=5)
    event.safety_review_requested_at = NOW - timedelta(minutes=1)
    db.flush()
    second = await review(client, other, event)

    assert (first.status_code, second.status_code) == (201, 201)
    history = (await client.get(f"{QUEUE}/{event.id}", headers=auth(officer))).json()["history"]
    assert [(h["outcome"], h["reviewer"]["id"], h["comments"]) for h in history] == [
        ("approved", str(other.id), "All clear."),
        ("rejected", str(officer.id), "Keep the side door clear and add a second exit."),
    ]
    assert history[1]["internal_notes"] == "Venue has history of blocked exits."


# --- AC 5: the coordinator is told ---


async def test_tc_us30a_24_the_coordinator_hears_the_outcome_comments_and_flagged_items(
    client: AsyncClient, event: Event, officer: User, notifier: FakeNotifier
) -> None:
    await review(client, officer, event, rejection())

    assert notifier.safety_reviews == [
        {
            "email": "casey.tan@smu.edu.sg",
            "request_reference": "ER-2026-000099",
            "event_name": "Community design workshop",
            "outcome": "rejected",
            "comments": "Keep the side door clear and add a second exit.",
            "issues": ["Emergency access"],
        }
    ]


async def test_tc_us30a_25_a_refused_review_tells_no_one_and_a_failing_notifier_does_not_undo_one(
    client: AsyncClient, db: Session, event: Event, officer: User, notifier: FakeNotifier, caplog: pytest.LogCaptureFixture
) -> None:
    await review(client, officer, event, approval(checklist={}))
    assert notifier.safety_reviews == []

    notifier.fail = True
    with caplog.at_level(logging.ERROR):
        response = await review(client, officer, event)

    assert response.status_code == 201
    assert len(reviews(db, event)) == 1
    assert "could not send the safety review notice" in caplog.text


# --- AC 7: the organiser's view ---


async def test_tc_us30a_26_the_organiser_and_coordinator_see_the_outcome_and_comments_but_not_internal_notes(
    client: AsyncClient, event: Event, officer: User, organiser: User, casey: User
) -> None:
    await review(client, officer, event, rejection())

    for reader in (organiser, casey):
        response = await client.get(f"/api/v1/event-requests/{event.id}/safety-reviews", headers=auth(reader))
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "rejected"
        [shown] = body["reviews"]
        assert (shown["outcome"], shown["comments"]) == ("rejected", "Keep the side door clear and add a second exit.")
        assert "internal_notes" not in shown
        assert "Venue has history" not in response.text


async def test_tc_us30a_27_only_the_events_readers_see_its_safety_outcome(
    client: AsyncClient, db: Session, event: Event, officer: User, organiser: User
) -> None:
    other_organiser = make_user(db, UserRole.ORGANISER)
    other_coordinator = make_user(db, UserRole.COORDINATOR)
    url = f"/api/v1/event-requests/{event.id}/safety-reviews"

    assert (await client.get(url, headers=auth(other_organiser))).status_code == 404
    assert (await client.get(url, headers=auth(other_coordinator))).status_code == 404
    assert (await client.get(url, headers=auth(officer))).status_code == 403
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers=auth(organiser))).json() == {"state": "pending", "reviews": []}


# --- who may review (D51, roles) ---


async def test_tc_us30a_28_only_a_safety_officer_reviews(
    client: AsyncClient, db: Session, event: Event, casey: User, organiser: User, venue_staff: User
) -> None:
    lead = make_user(db, UserRole.COORDINATOR_LEAD)
    for caller in (casey, organiser, venue_staff, lead):
        for method, path in (("GET", QUEUE), ("GET", f"{QUEUE}/{event.id}"), ("POST", f"{QUEUE}/{event.id}")):
            response = await client.request(method, path, headers=auth(caller), json=approval() if method == "POST" else None)
            assert response.status_code == 403, (caller.roles, method)
    assert (await client.get(QUEUE)).status_code == 401
    assert (await client.post(f"{QUEUE}/{event.id}", json=approval())).status_code == 401


async def test_tc_us30a_29_a_safety_officer_does_not_review_an_event_they_created_or_coordinate(
    client: AsyncClient, db: Session, event: Event, venue: Venue
) -> None:
    both = make_user(db, UserRole.SAFETY_OFFICER, UserRole.COORDINATOR)
    event.created_by_user_id = both.id
    db.flush()
    created = await review(client, both, event)
    event.created_by_user_id = None
    event.coordinator_id = both.id
    db.flush()
    coordinated = await review(client, both, event)

    assert [(r.status_code, r.json()) for r in (created, coordinated)] == [(403, {"code": "SELF_DECISION_NOT_ALLOWED"})] * 2
    assert reviews(db, event) == []


# --- AC 3, 8: nothing moves on without an approved review ---


async def test_tc_us30a_30_a_confirmed_event_without_an_approved_safety_review_does_not_move_to_preparation(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    event.status = EventStatus.CONFIRMED
    event.start_at, event.end_at, event.capacity, event.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    blocked = await client.post(f"/api/v1/event-requests/{event.id}/preparation", headers=auth(casey))

    assert (blocked.status_code, blocked.json()) == (409, {"code": "SAFETY_NOT_APPROVED"})
    event.safety_approved_at, event.safety_approved_by_user_id = NOW, officer.id
    db.flush()
    assert (await client.post(f"/api/v1/event-requests/{event.id}/preparation", headers=auth(casey))).status_code == 200


async def test_tc_us30a_31_the_seeded_demo_is_in_the_queue_and_a_reseed_resets_it(client: AsyncClient, db: Session) -> None:
    from app.seed import EVENT_COORDINATOR_EMAIL, SAFETY_OFFICER_EMAIL, SAFETY_REVIEW_EVENT, seed, seed_id

    seed(db, now=NOW)
    officer = db.scalars(select(User).where(User.email == SAFETY_OFFICER_EMAIL)).one()
    demo = db.get(Event, seed_id("event", SAFETY_REVIEW_EVENT.slug))

    assert str(demo.id) in [row["event_id"] for row in await queue(client, officer)]
    assert (await review(client, officer, demo)).status_code == 201
    assert str(demo.id) not in [row["event_id"] for row in await queue(client, officer)]

    seed(db, now=NOW)
    db.refresh(demo)
    assert demo.safety_approved_at is None and reviews(db, demo) == []
    assert str(demo.id) in [row["event_id"] for row in await queue(client, officer)]
    assert EVENT_COORDINATOR_EMAIL


# --- US30b (SCRUM-100): request changes ---

DONE = "/api/v1/event-requests/{}/safety-review-request"


def changes(**overrides: object) -> dict:
    return {
        "outcome": "changes_requested",
        "checklist": ok(layout={"result": "issue", "comment": "Aisles too narrow"}),
        "comments": "Widen the aisles and move the stage back.",
        "internal_notes": "Second time this layout has come up.",
        "areas": ["layout", "venue"],
    } | overrides


async def safety_item(client: AsyncClient, coordinator: User, event: Event) -> dict:
    readiness = (await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(coordinator))).json()
    return next(item for item in readiness["items"] if item["kind"] == "safety")


async def test_tc_us30b_01_requesting_changes_records_the_areas_and_leaves_the_event_where_it_is(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    response = await review(client, officer, event, changes())

    assert response.status_code == 201
    body = response.json()
    assert (body["outcome"], body["areas"], body["internal_notes"]) == (
        "changes_requested", ["venue", "layout"], "Second time this layout has come up.",
    )
    [row] = reviews(db, event)
    assert (row.outcome, row.areas, row.reviewer_id) == ("changes_requested", ["venue", "layout"], officer.id)
    assert (event.status, event.safety_approved_at) == (EventStatus.APPROVED, None)
    item = await safety_item(client, casey, event)
    assert not item["complete"]
    assert item["detail"] == (
        "The Safety Officer asked for changes to Venue, Layout: Widen the aisles and move the stage back. "
        "Make the changes, then mark them done."
    )
    confirm = await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(casey))
    assert (confirm.status_code, confirm.json()["code"]) == (409, "EVENT_NOT_READY")


async def test_tc_us30b_02_a_planning_event_stays_in_planning(
    client: AsyncClient, db: Session, event: Event, officer: User
) -> None:
    event.status = EventStatus.PLANNING
    event.start_at, event.end_at, event.capacity, event.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    assert (await review(client, officer, event, changes())).status_code == 201
    db.refresh(event)

    assert event.status == EventStatus.PLANNING


async def test_tc_us30b_03_comments_and_at_least_one_area_are_required(
    client: AsyncClient, db: Session, event: Event, officer: User
) -> None:
    cases = [
        (changes(areas=None), ["areas"]),
        (changes(areas=[]), ["areas"]),
        (changes(comments=None), ["comments"]),
        (changes(comments="   "), ["comments"]),
        (changes(comments=None, areas=[]), ["comments", "areas"]),
    ]
    for body, fields in cases:
        response = await review(client, officer, event, body)
        assert (response.status_code, response.json()) == (422, {"code": "MISSING_REQUIRED_FIELD", "fields": fields})

    assert reviews(db, event) == []


async def test_tc_us30b_04_an_unknown_area_is_refused_and_areas_belong_to_a_request_for_changes_only(
    client: AsyncClient, db: Session, event: Event, officer: User
) -> None:
    unknown = await review(client, officer, event, changes(areas=["venue", "catering"]))
    on_approval = await review(client, officer, event, approval(areas=["venue"]))
    on_rejection = await review(client, officer, event, rejection(areas=["layout"]))

    assert [(r.status_code, r.json()["code"], r.json()["fields"]) for r in (unknown, on_approval, on_rejection)] == [
        (422, "INVALID_SAFETY_REVIEW", ["areas"]),
    ] * 3
    assert unknown.json()["items"] == ["catering"]
    assert reviews(db, event) == []


async def test_tc_us30b_05_a_duplicate_area_is_kept_once_in_the_forms_order(
    client: AsyncClient, event: Event, officer: User
) -> None:
    response = await review(client, officer, event, changes(areas=["other", "venue", "other", "equipment"]))

    assert response.json()["areas"] == ["venue", "equipment", "other"]


async def test_tc_us30b_06_the_checklist_is_still_answered_and_may_carry_issues_or_none(
    client: AsyncClient, db: Session, event: Event, officer: User
) -> None:
    missing = await review(client, officer, event, changes(checklist={}))
    assert (missing.status_code, missing.json()["code"]) == (422, "MISSING_REQUIRED_FIELD")
    assert reviews(db, event) == []

    clean = await review(client, officer, event, changes(checklist=ok()))
    assert clean.status_code == 201


async def test_tc_us30b_07_the_database_refuses_a_request_for_changes_without_comments_or_areas(
    db: Session, event: Event, officer: User
) -> None:
    for comments, areas in ((None, ["venue"]), ("  ", ["venue"]), ("Fix it", None), ("Fix it", [])):
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(SafetyReview(
                    event_id=event.id, reviewer_id=officer.id, outcome="changes_requested", checklist=ok(),
                    comments=comments, areas=areas, created_at=NOW,
                ))
                db.flush()


async def test_tc_us30b_08_nothing_is_reset_the_venue_booking_and_equipment_stay_as_they_were(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    line = make_line(db, event=event, equipment_type=make_type(db, "Projector"), requested_by=casey, status=EquipmentLineStatus.APPROVED, quantity=1)
    reserve(db, line, db.get(User, line.reviewed_by_user_id))
    before = [(b.status, b.is_primary) for b in event.venue_bookings] if hasattr(event, "venue_bookings") else None

    await review(client, officer, event, changes(areas=["venue", "equipment"]))
    db.refresh(line)
    db.expire_all()

    assert line.status == EquipmentLineStatus.APPROVED
    assert db.scalars(select(Event.safety_approved_at).where(Event.id == event.id)).one() is None
    readiness = (await client.get(f"/api/v1/event-requests/{event.id}/readiness", headers=auth(casey))).json()
    complete = {item["kind"]: item["complete"] for item in readiness["items"]}
    assert (complete["venue"], complete["equipment"]) == (True, True)
    assert before is None or before == [(b.status, b.is_primary) for b in event.venue_bookings]


async def test_tc_us30b_09_the_coordinator_hears_the_comments_and_the_areas(
    client: AsyncClient, event: Event, officer: User, notifier: FakeNotifier
) -> None:
    await review(client, officer, event, changes())

    assert notifier.safety_reviews == []
    assert notifier.safety_changes == [
        {
            "email": "casey.tan@smu.edu.sg",
            "request_reference": "ER-2026-000099",
            "event_name": "Community design workshop",
            "comments": "Widen the aisles and move the stage back.",
            "areas": ["Venue", "Layout"],
            "issues": ["Room layout"],
        }
    ]


async def test_tc_us30b_10_a_refused_request_tells_no_one_and_a_failing_notifier_does_not_undo_one(
    client: AsyncClient, db: Session, event: Event, officer: User, notifier: FakeNotifier, caplog: pytest.LogCaptureFixture
) -> None:
    await review(client, officer, event, changes(areas=[]))
    assert notifier.safety_changes == []

    notifier.fail = True
    with caplog.at_level(logging.ERROR):
        response = await review(client, officer, event, changes())

    assert response.status_code == 201
    assert len(reviews(db, event)) == 1
    assert "could not send the safety review notice" in caplog.text


async def test_tc_us30b_11_the_event_leaves_the_queue_and_waits_for_the_coordinator(
    client: AsyncClient, event: Event, officer: User
) -> None:
    await review(client, officer, event, changes())

    again = await review(client, officer, event)

    assert await queue(client, officer) == []
    assert (again.status_code, again.json()["reason"]) == (409, "awaiting_revision")


async def test_tc_us30b_12_marking_the_changes_done_brings_it_back_to_the_queue_for_another_review(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    await review(client, officer, event, changes())

    done = await client.post(DONE.format(event.id), headers=auth(casey))

    assert done.status_code == 200
    assert done.json()["state"] == "pending"
    [row] = await queue(client, officer)
    assert (row["event_id"], row["resent"]) == (str(event.id), True)
    assert (await safety_item(client, casey, event))["detail"] == "Sent for another safety review."


async def test_tc_us30b_13_the_second_review_is_made_and_both_stay_in_the_history(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    await review(client, officer, event, changes())
    await client.post(DONE.format(event.id), headers=auth(casey))

    # The clock is frozen, so a later review needs a later instant to sort after the earlier one.
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=5)
    approved = await review(client, officer, event)

    assert approved.status_code == 201
    history = (await client.get(f"{QUEUE}/{event.id}", headers=auth(officer))).json()["history"]
    assert [(h["outcome"], h["areas"]) for h in history] == [("approved", None), ("changes_requested", ["venue", "layout"])]
    assert history[1]["internal_notes"] == "Second time this layout has come up."
    assert (await client.post(f"/api/v1/event-requests/{event.id}/confirmation", headers=auth(casey))).status_code == 200


async def test_tc_us30b_14_changes_can_be_requested_again_after_the_second_review(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User
) -> None:
    await review(client, officer, event, changes())
    await client.post(DONE.format(event.id), headers=auth(casey))

    # The clock is frozen, so a later review needs a later instant to count as after the send-back.
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(minutes=5)
    second = await review(client, officer, event, changes(areas=["equipment"], comments="Move the speakers."))
    state = (await client.get(f"/api/v1/event-requests/{event.id}/safety-reviews", headers=auth(casey))).json()

    assert second.status_code == 201
    assert state["state"] == "changes_requested"
    assert [(r["outcome"], r["areas"]) for r in state["reviews"]] == [
        ("changes_requested", ["equipment"]), ("changes_requested", ["venue", "layout"]),
    ]


async def test_tc_us30b_15_marking_changes_done_is_refused_when_there_is_nothing_to_mark_and_to_anyone_else(
    client: AsyncClient, db: Session, event: Event, casey: User, officer: User, organiser: User
) -> None:
    url = DONE.format(event.id)
    await review(client, officer, event, changes())
    other = make_user(db, UserRole.COORDINATOR)

    assert (await client.post(url, headers=auth(other))).status_code == 404
    assert (await client.post(url, headers=auth(organiser))).status_code == 403
    assert (await client.post(url, headers=auth(officer))).status_code == 403
    assert (await client.post(url)).status_code == 401
    first = await client.post(url, headers=auth(casey))
    twice = await client.post(url, headers=auth(casey))

    assert (first.status_code, twice.status_code, twice.json()["reason"]) == (200, 409, "already_requested")


async def test_tc_us30b_16_the_organiser_coordinator_and_lead_see_the_comments_and_areas_but_not_internal_notes(
    client: AsyncClient, db: Session, event: Event, officer: User, organiser: User, casey: User
) -> None:
    await review(client, officer, event, changes())
    lead = make_user(db, UserRole.COORDINATOR_LEAD)

    for reader in (organiser, casey, lead):
        response = await client.get(f"/api/v1/event-requests/{event.id}/safety-reviews", headers=auth(reader))
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "changes_requested"
        [shown] = body["reviews"]
        assert (shown["outcome"], shown["areas"], shown["comments"]) == (
            "changes_requested", ["venue", "layout"], "Widen the aisles and move the stage back.",
        )
        assert "internal_notes" not in shown
        assert "Second time" not in response.text


async def test_tc_us30b_17_only_a_safety_officer_requests_changes_and_not_for_an_event_they_coordinate(
    client: AsyncClient, db: Session, event: Event, casey: User, organiser: User
) -> None:
    for caller in (casey, organiser):
        assert (await review(client, caller, event, changes())).status_code == 403
    assert (await review(client, None, event, changes())).status_code == 401
    own = make_user(db, UserRole.SAFETY_OFFICER)
    event.coordinator_id = own.id
    db.flush()

    refused = await review(client, own, event, changes())

    assert (refused.status_code, refused.json()["code"]) == (403, "SELF_DECISION_NOT_ALLOWED")
    assert reviews(db, event) == []


@pytest.mark.parametrize(
    "status", [EventStatus.UNDER_REVIEW, EventStatus.CONFIRMED, EventStatus.PREPARATION, EventStatus.CANCELLED, EventStatus.REJECTED]
)
async def test_tc_us30b_18_only_an_approved_or_planning_event_is_sent_for_changes(
    client: AsyncClient, db: Session, event: Event, officer: User, status: EventStatus
) -> None:
    event.status = status
    event.start_at, event.end_at, event.capacity, event.delivery_mode = STARTS, STARTS + timedelta(hours=2), 35, DeliveryMode.IN_PERSON
    db.flush()

    refused = await review(client, officer, event, changes())

    assert (refused.status_code, refused.json()["reason"]) == (409, "status")
    assert reviews(db, event) == []


async def test_tc_us30b_19_the_seeded_demo_can_be_sent_for_changes_and_a_reseed_forgets_it(
    client: AsyncClient, db: Session
) -> None:
    from app.seed import SAFETY_REVIEW_EVENT, seed, seed_id

    seed(db)
    demo = db.get(Event, seed_id("event", SAFETY_REVIEW_EVENT.slug))
    officer = db.scalars(select(User).where(User.roles.any(UserRole.SAFETY_OFFICER))).first()

    sent = await review(client, officer, demo, changes())
    assert sent.status_code == 201
    seed(db)

    assert reviews(db, demo) == []
    assert str(demo.id) in [row["event_id"] for row in await queue(client, officer)]

