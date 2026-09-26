from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.event.models import EventStatus
from tests.factories import NOW, make_attendee, make_event, make_registration, make_registration_field

pytestmark = pytest.mark.anyio


def auth(attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


async def test_tc_us3_01_lists_only_confirmed_registration_open_events(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)

    eligible = make_event(db, name="Open Tech Talk")
    make_event(db, name="Draft Event", status=EventStatus.DRAFT)
    make_event(db, name="Submitted Event", status=EventStatus.SUBMITTED)
    make_event(db, name="Cancelled Event", status=EventStatus.CANCELLED)
    make_event(db, name="Disabled Event", registration_enabled=False)
    make_event(
        db,
        name="Not Open Yet",
        registration_opens_at=NOW + timedelta(days=1),
        registration_closes_at=NOW + timedelta(days=10),
    )
    make_event(
        db,
        name="Already Closed",
        registration_opens_at=NOW - timedelta(days=10),
        registration_closes_at=NOW - timedelta(days=1),
    )
    make_event(
        db,
        name="Already Ended",
        start_at=NOW - timedelta(days=1),
        end_at=NOW - timedelta(hours=1),
        registration_opens_at=NOW - timedelta(days=10),
        registration_closes_at=NOW - timedelta(hours=2),
    )

    response = await client.get("/api/v1/events/available", headers=auth(attendee))

    assert response.status_code == 200
    names = [e["name"] for e in response.json()["events"]]
    assert names == [eligible.name]


async def test_available_event_reports_seats_and_registration_fields(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    event = make_event(db, capacity=5)
    make_registration(db, event, make_attendee(db))
    make_registration_field(db, event, field_key="dietary", required=False)

    response = await client.get("/api/v1/events/available", headers=auth(attendee))

    body = response.json()["events"][0]
    assert body["seats_remaining"] == 4
    assert body["is_full"] is False
    assert body["already_registered"] is False
    assert body["registration_fields"] == [
        {"field_key": "dietary", "label": "Dietary requirements", "field_type": "text", "options": None, "required": False}
    ]


async def test_already_registered_is_true_for_the_calling_attendee_only(
    client: AsyncClient, db: Session
) -> None:
    attendee = make_attendee(db)
    other = make_attendee(db)
    event = make_event(db)
    make_registration(db, event, attendee)

    mine = await client.get("/api/v1/events/available", headers=auth(attendee))
    theirs = await client.get("/api/v1/events/available", headers=auth(other))

    assert mine.json()["events"][0]["already_registered"] is True
    assert theirs.json()["events"][0]["already_registered"] is False


async def test_available_events_requires_an_attendee_header(client: AsyncClient, db: Session) -> None:
    response = await client.get("/api/v1/events/available")

    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHENTICATED"}
