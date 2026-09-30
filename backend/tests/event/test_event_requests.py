import re
import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.user.models import User, UserRole
from tests.factories import NOW, make_event

pytestmark = pytest.mark.anyio


def make_user(db: Session, role: UserRole = UserRole.ORGANISER, *, active: bool = True) -> User:
    user = User(
        email=f"{uuid.uuid4().hex}@smu.edu.sg",
        role=role,
        is_active=active,
    )
    db.add(user)
    db.flush()
    return user


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def complete_request(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Community design workshop",
        "event_category": "Workshop",
        "purpose": "Plan a community design session",
        "preferred_dates": [(NOW.date() + timedelta(days=7)).isoformat()],
        "preferred_start_time": "09:00:00",
        "preferred_end_time": "11:00:00",
        "expected_attendees": 24,
    }
    body.update(overrides)
    return body


async def create_draft(client: AsyncClient, user: User, **fields: object) -> dict[str, object]:
    response = await client.post("/api/v1/event-requests", headers=auth(user), json=fields)
    assert response.status_code == 201
    return response.json()


async def submit(client: AsyncClient, user: User, request_id: str) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/event-requests/{request_id}/submit", headers=auth(user)
    )
    assert response.status_code == 200
    return response.json()


async def test_tc_us1_01_saves_incomplete_request_as_draft(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)

    response = await client.post(
        "/api/v1/event-requests",
        headers=auth(organiser),
        json={"name": "Partially planned workshop"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert response.json()["name"] == "Partially planned workshop"
    assert response.json()["request_reference"] is None


async def test_tc_us1_02_owner_can_resume_and_update_draft(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(client, organiser, name="Draft")

    updated = await client.patch(
        f"/api/v1/event-requests/{draft['id']}",
        headers=auth(organiser),
        json={"purpose": "Finish the proposal"},
    )
    retrieved = await client.get(
        f"/api/v1/event-requests/{draft['id']}", headers=auth(organiser)
    )
    listed = await client.get("/api/v1/me/event-requests", headers=auth(organiser))

    assert updated.status_code == 200
    assert retrieved.status_code == 200
    assert retrieved.json()["purpose"] == "Finish the proposal"
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["event_requests"]] == [draft["id"]]


async def test_tc_us1_03_round_trips_optional_requirements_and_false(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(
        client,
        organiser,
        name="Optional fields",
        registration_required=False,
        room_layout_preference="Classroom",
        accessibility_needs="Step-free access",
        equipment_needs="Projector",
    )

    retrieved = await client.get(
        f"/api/v1/event-requests/{draft['id']}", headers=auth(organiser)
    )

    assert retrieved.status_code == 200
    assert retrieved.json()["registration_required"] is False
    assert retrieved.json()["room_layout_preference"] == "Classroom"
    assert retrieved.json()["accessibility_needs"] == "Step-free access"
    assert retrieved.json()["equipment_needs"] == "Projector"


async def test_tc_us1_04_submits_request_with_all_mandatory_fields(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(client, organiser, **complete_request())

    response = await client.post(
        f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"


async def test_tc_us1_05_missing_fields_are_reported_without_submitting(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(client, organiser)

    response = await client.post(
        f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser)
    )
    retrieved = await client.get(
        f"/api/v1/event-requests/{draft['id']}", headers=auth(organiser)
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "MISSING_REQUIRED_FIELD",
        "fields": [
            "name",
            "event_category",
            "purpose",
            "preferred_dates",
            "preferred_start_time",
            "preferred_end_time",
            "expected_attendees",
        ],
    }
    assert retrieved.json()["status"] == "draft"


async def test_tc_us1_06_rejects_past_or_duplicate_preferred_dates(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    past = (NOW.date() - timedelta(days=1)).isoformat()
    duplicate = (NOW.date() + timedelta(days=4)).isoformat()

    for dates in ([past], [duplicate, duplicate]):
        draft = await create_draft(client, organiser, **complete_request(preferred_dates=dates))
        response = await client.post(
            f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser)
        )
        assert response.status_code == 422
        assert response.json()["code"] == "INVALID_EVENT_REQUEST"
        assert "preferred_dates" in response.json()["fields"]


async def test_tc_us1_06_returns_preferred_dates_sorted(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    dates = [
        (NOW.date() + timedelta(days=9)).isoformat(),
        (NOW.date() + timedelta(days=3)).isoformat(),
    ]
    draft = await create_draft(client, organiser, **complete_request(preferred_dates=dates))

    response = await client.post(
        f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser)
    )

    assert response.status_code == 200
    assert response.json()["preferred_dates"] == sorted(dates)


async def test_tc_us1_07_requires_both_preferred_times(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(
        client,
        organiser,
        **complete_request(preferred_start_time=None, preferred_end_time=None),
    )

    response = await client.post(
        f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "MISSING_REQUIRED_FIELD"
    assert "preferred_start_time" in response.json()["fields"]
    assert "preferred_end_time" in response.json()["fields"]


async def test_tc_us1_07_requires_start_time_before_end_time(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(
        client,
        organiser,
        **complete_request(preferred_start_time="11:00:00", preferred_end_time="09:00:00"),
    )

    response = await client.post(
        f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_EVENT_REQUEST"
    assert "preferred_start_time" in response.json()["fields"]


async def test_tc_us1_08_requires_at_least_one_expected_attendee(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    response = await client.post(
        "/api/v1/event-requests",
        headers=auth(organiser),
        json=complete_request(expected_attendees=0),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_EVENT_REQUEST"
    assert "expected_attendees" in response.json()["fields"]


async def test_tc_us1_09_records_submitter_and_timestamp(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(client, organiser, **complete_request())

    result = await submit(client, organiser, draft["id"])
    event = db.scalar(select(Event).where(Event.id == uuid.UUID(draft["id"])))

    assert result["submitted_by_user_id"] == str(organiser.id)
    assert result["submitted_at"] is not None
    assert event is not None
    assert event.status == EventStatus.SUBMITTED
    assert event.submitted_by_user_id == organiser.id
    assert event.submitted_at is not None


async def test_tc_us1_10_generates_unique_reference_numbers(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    references = []
    for _ in range(2):
        draft = await create_draft(client, organiser, **complete_request())
        result = await submit(client, organiser, draft["id"])
        references.append(result["request_reference"])

    assert len(set(references)) == 2
    assert all(re.fullmatch(r"ER-2026-\d{6}", reference) for reference in references)


async def test_tc_us1_11_draft_has_no_reference_and_repeat_submit_conflicts(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(client, organiser, **complete_request())
    first = await submit(client, organiser, draft["id"])
    second = await client.post(
        f"/api/v1/event-requests/{draft['id']}/submit", headers=auth(organiser)
    )

    assert draft["request_reference"] is None
    assert second.status_code == 409
    assert second.json() == {"code": "EVENT_REQUEST_LOCKED"}
    assert first["request_reference"]


async def test_tc_us1_12_submitted_request_cannot_be_edited(
    client: AsyncClient, db: Session
) -> None:
    organiser = make_user(db)
    draft = await create_draft(client, organiser, **complete_request())
    submitted = await submit(client, organiser, draft["id"])

    response = await client.patch(
        f"/api/v1/event-requests/{draft['id']}",
        headers=auth(organiser),
        json={"purpose": "Changed after submission"},
    )
    retrieved = await client.get(
        f"/api/v1/event-requests/{draft['id']}", headers=auth(organiser)
    )

    assert response.status_code == 409
    assert response.json() == {"code": "EVENT_REQUEST_LOCKED"}
    assert retrieved.json()["purpose"] == submitted["purpose"]


async def test_tc_us1_13_other_organiser_cannot_access_draft(
    client: AsyncClient, db: Session
) -> None:
    owner = make_user(db)
    other = make_user(db)
    draft = await create_draft(client, owner, name="Private draft")
    request_url = f"/api/v1/event-requests/{draft['id']}"

    get_response = await client.get(request_url, headers=auth(other))
    patch_response = await client.patch(request_url, headers=auth(other), json={"name": "Intrusion"})
    submit_response = await client.post(f"{request_url}/submit", headers=auth(other))

    assert get_response.status_code == 404
    assert patch_response.status_code == 404
    assert submit_response.status_code == 404
    assert submit_response.json() == {"code": "NOT_FOUND"}


async def test_tc_us1_14_submitted_visibility_and_draft_privacy(
    client: AsyncClient, db: Session
) -> None:
    owner = make_user(db)
    other_organiser = make_user(db)
    coordinator = make_user(db, UserRole.COORDINATOR)
    operations_manager = make_user(db, UserRole.OPERATIONS_MANAGER)
    submitted_draft = await create_draft(client, owner, **complete_request())
    submitted = await submit(client, owner, submitted_draft["id"])
    private_draft = await create_draft(client, owner, name="Still private")
    confirmed_event = make_event(db)

    for reader in (owner, coordinator, operations_manager):
        response = await client.get(
            f"/api/v1/event-requests/{submitted_draft['id']}", headers=auth(reader)
        )
        assert response.status_code == 200
        assert response.json()["request_reference"] == submitted["request_reference"]

    for reader in (coordinator, operations_manager, other_organiser):
        response = await client.get(
            f"/api/v1/event-requests/{private_draft['id']}", headers=auth(reader)
        )
        assert response.status_code == 404

    other_read = await client.get(
        f"/api/v1/event-requests/{submitted_draft['id']}", headers=auth(other_organiser)
    )
    assert other_read.status_code == 404
    assert other_read.json() == {"code": "NOT_FOUND"}

    unrelated_event = await client.get(
        f"/api/v1/event-requests/{confirmed_event.id}", headers=auth(coordinator)
    )
    assert unrelated_event.status_code == 404


async def test_tc_us1_15_enforces_identity_activity_and_role(
    client: AsyncClient, db: Session
) -> None:
    inactive_organiser = make_user(db, active=False)
    attendee = make_user(db, UserRole.ATTENDEE)
    missing = await client.post("/api/v1/event-requests", json={"name": "No identity"})
    unknown = await client.post(
        "/api/v1/event-requests",
        headers={"X-User-Id": str(uuid.uuid4())},
        json={"name": "Unknown user"},
    )
    inactive = await client.post(
        "/api/v1/event-requests", headers=auth(inactive_organiser), json={"name": "Inactive"}
    )
    wrong_role = await client.post(
        "/api/v1/event-requests", headers=auth(attendee), json={"name": "Attendee"}
    )

    assert missing.status_code == 401
    assert missing.json() == {"code": "UNAUTHENTICATED"}
    assert unknown.status_code == 401
    assert inactive.status_code == 403
    assert wrong_role.status_code == 403