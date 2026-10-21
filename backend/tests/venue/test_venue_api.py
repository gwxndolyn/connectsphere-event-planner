"""US20 venue catalogue, PR 2 (SCRUM-87): the venue endpoints, the access rule and validation.
Test cases: docs/testing/US20-venue-catalogue.md."""

import uuid
from datetime import time

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.user.models import User, UserRole
from app.venue import service as venue_service_module
from app.venue.models import Venue
from tests.factories import NOW

pytestmark = pytest.mark.anyio

NON_STAFF_ROLES = (UserRole.ORGANISER, UserRole.COORDINATOR, UserRole.ATTENDEE)


def make_user(db: Session, role: UserRole, *, active: bool = True) -> User:
    user = User(email=f"{uuid.uuid4().hex}@smu.edu.sg", role=role, is_active=active)
    db.add(user)
    db.flush()
    return user


def make_staff(db: Session) -> User:
    # DECISION-PENDING: D19 — operations_manager stands in for Venue Staff until US16b.
    return make_user(db, UserRole.OPERATIONS_MANAGER)


def auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


def venue_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "Test Seminar Room",
        "location": "Test Building, Level 1",
        "capacity": 30,
        "facilities": ["projector", "wifi"],
        "accessibility_features": ["wheelchair"],
        "room_layouts": ["classroom"],
        "opens_at": "09:00",
        "closes_at": "18:00",
        "setup_minutes": 15,
        "turnaround_minutes": 10,
    }
    body.update(overrides)
    return body


def make_venue(db: Session, **overrides: object) -> Venue:
    fields: dict[str, object] = {
        "name": "Stored Room",
        "location": "Stored Building",
        "capacity": 40,
        "facilities": ["projector"],
        "accessibility_features": [],
        "room_layouts": ["theatre"],
        "opens_at": time(8, 0),
        "closes_at": time(20, 0),
        "setup_minutes": 30,
        "turnaround_minutes": 15,
    }
    venue = Venue(**(fields | overrides))
    db.add(venue)
    db.flush()
    return venue


def names(response) -> list[str]:
    return [venue["name"] for venue in response.json()["venues"]]


def lock_buffers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(venue_service_module, "has_approved_future_bookings", lambda *_: True)


# --- TC-US20-01 (API create) ---


async def test_tc_us20_01_staff_create_a_venue_with_every_field(client: AsyncClient, db: Session) -> None:
    staff = make_staff(db)

    response = await client.post("/api/v1/venues", headers=auth(staff), json=venue_body())

    assert response.status_code == 201
    created = response.json()
    assert created["is_active"] is True
    assert created["name"] == "Test Seminar Room"
    assert created["location"] == "Test Building, Level 1"
    assert created["capacity"] == 30
    assert created["facilities"] == ["projector", "wifi"]
    assert created["accessibility_features"] == ["wheelchair"]
    assert created["room_layouts"] == ["classroom"]
    assert created["opens_at"] == "09:00:00"
    assert created["closes_at"] == "18:00:00"
    assert created["setup_minutes"] == 15
    assert created["turnaround_minutes"] == 10

    read = await client.get(f"/api/v1/venues/{created['id']}", headers=auth(staff))
    assert read.status_code == 200
    assert read.json() == created


async def test_tc_us20_01_buffers_and_tags_default_when_left_out(client: AsyncClient, db: Session) -> None:
    body = venue_body()
    for key in ("facilities", "accessibility_features", "room_layouts", "setup_minutes", "turnaround_minutes"):
        del body[key]

    response = await client.post("/api/v1/venues", headers=auth(make_staff(db)), json=body)

    assert response.status_code == 201
    assert response.json()["facilities"] == []
    assert response.json()["setup_minutes"] == 0
    assert response.json()["turnaround_minutes"] == 0


# --- TC-US20-02 edits and the buffer lock ---


async def test_tc_us20_02_patch_changes_only_the_fields_sent(client: AsyncClient, db: Session) -> None:
    venue = make_venue(db)

    response = await client.patch(
        f"/api/v1/venues/{venue.id}", headers=auth(make_staff(db)), json={"name": "Renamed Room", "capacity": 55}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Room"
    assert response.json()["capacity"] == 55
    assert response.json()["location"] == "Stored Building"
    assert response.json()["setup_minutes"] == 30


@pytest.mark.parametrize("field", ["setup_minutes", "turnaround_minutes"])
async def test_tc_us20_02_buffer_edit_refused_while_approved_future_bookings_exist(
    client: AsyncClient, db: Session, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    venue = make_venue(db)
    lock_buffers(monkeypatch)

    response = await client.patch(f"/api/v1/venues/{venue.id}", headers=auth(make_staff(db)), json={field: 45})

    assert response.status_code == 409
    assert response.json()["code"] == "VENUE_BUFFERS_LOCKED"
    assert response.json()["fields"] == [field]
    assert "approved future bookings" in response.json()["message"]
    db.expire_all()
    assert db.get(Venue, venue.id).setup_minutes == 30
    assert db.get(Venue, venue.id).turnaround_minutes == 15


async def test_tc_us20_02_other_fields_stay_editable_while_buffers_are_locked(
    client: AsyncClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    venue = make_venue(db)
    lock_buffers(monkeypatch)

    response = await client.patch(
        f"/api/v1/venues/{venue.id}", headers=auth(make_staff(db)), json={"capacity": 60, "closes_at": "21:00"}
    )

    assert response.status_code == 200
    assert response.json()["capacity"] == 60
    assert response.json()["closes_at"] == "21:00:00"


# --- TC-US20-03 deactivate and reactivate ---


async def test_tc_us20_03_deactivated_venue_leaves_the_list_and_can_come_back(
    client: AsyncClient, db: Session
) -> None:
    venue = make_venue(db, name="Soon Inactive Room")
    staff = make_staff(db)
    organiser = make_user(db, UserRole.ORGANISER)

    deactivated = await client.post(f"/api/v1/venues/{venue.id}/deactivate", headers=auth(staff))
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    again = await client.post(f"/api/v1/venues/{venue.id}/deactivate", headers=auth(staff))
    assert again.status_code == 200
    assert again.json()["is_active"] is False

    assert "Soon Inactive Room" not in names(await client.get("/api/v1/venues", headers=auth(organiser)))
    assert (await client.get(f"/api/v1/venues/{venue.id}", headers=auth(organiser))).status_code == 404

    # Staff may fix details on an inactive venue before reactivating it.
    edited = await client.patch(f"/api/v1/venues/{venue.id}", headers=auth(staff), json={"capacity": 25})
    assert edited.status_code == 200
    assert edited.json()["capacity"] == 25
    assert edited.json()["is_active"] is False

    reactivated = await client.post(f"/api/v1/venues/{venue.id}/reactivate", headers=auth(staff))
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True
    assert (await client.post(f"/api/v1/venues/{venue.id}/reactivate", headers=auth(staff))).status_code == 200
    assert "Soon Inactive Room" in names(await client.get("/api/v1/venues", headers=auth(organiser)))


# --- TC-US20-04 (API errors naming the field) ---


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"capacity": 0}, "capacity"),
        ({"capacity": -1}, "capacity"),
        ({"opens_at": "18:00", "closes_at": "18:00"}, "closes_at"),
        ({"opens_at": "19:00", "closes_at": "18:00"}, "closes_at"),
        ({"setup_minutes": -1}, "setup_minutes"),
        ({"turnaround_minutes": -5}, "turnaround_minutes"),
        ({"name": "   "}, "name"),
        ({"location": ""}, "location"),
    ],
)
async def test_tc_us20_04_invalid_values_name_the_field(
    client: AsyncClient, db: Session, overrides: dict, field: str
) -> None:
    response = await client.post("/api/v1/venues", headers=auth(make_staff(db)), json=venue_body(**overrides))

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_VENUE"
    assert response.json()["fields"] == [field]
    assert response.json()["errors"][field]


async def test_tc_us20_04_every_invalid_field_is_reported_at_once(client: AsyncClient, db: Session) -> None:
    response = await client.post(
        "/api/v1/venues",
        headers=auth(make_staff(db)),
        json=venue_body(capacity=0, setup_minutes=-1, opens_at="20:00", closes_at="08:00"),
    )

    assert response.status_code == 422
    assert set(response.json()["fields"]) == {"capacity", "setup_minutes", "closes_at"}


async def test_tc_us20_04_zero_minute_buffers_are_valid(client: AsyncClient, db: Session) -> None:
    response = await client.post(
        "/api/v1/venues", headers=auth(make_staff(db)), json=venue_body(setup_minutes=0, turnaround_minutes=0)
    )

    assert response.status_code == 201


# --- TC-US20-06 other roles read but can't write ---


@pytest.mark.parametrize("role", NON_STAFF_ROLES)
async def test_tc_us20_06_other_roles_can_read_venues(client: AsyncClient, db: Session, role: UserRole) -> None:
    venue = make_venue(db, name="Readable Room")
    user = make_user(db, role)

    listed = await client.get("/api/v1/venues", headers=auth(user))
    read = await client.get(f"/api/v1/venues/{venue.id}", headers=auth(user))

    assert listed.status_code == 200
    assert "Readable Room" in names(listed)
    assert read.status_code == 200
    assert read.json()["name"] == "Readable Room"


@pytest.mark.parametrize("role", NON_STAFF_ROLES)
async def test_tc_us20_06_other_roles_cannot_change_venues(client: AsyncClient, db: Session, role: UserRole) -> None:
    venue = make_venue(db)
    headers = auth(make_user(db, role))

    responses = [
        await client.post("/api/v1/venues", headers=headers, json=venue_body()),
        await client.patch(f"/api/v1/venues/{venue.id}", headers=headers, json={"capacity": 99}),
        await client.post(f"/api/v1/venues/{venue.id}/deactivate", headers=headers),
        await client.post(f"/api/v1/venues/{venue.id}/reactivate", headers=headers),
    ]

    assert [r.status_code for r in responses] == [403] * 4
    assert all(r.json()["code"] == "FORBIDDEN" for r in responses)
    db.expire_all()
    assert db.get(Venue, venue.id).capacity == 40
    assert db.get(Venue, venue.id).is_active is True


async def test_tc_us20_06_inactive_staff_member_cannot_write(client: AsyncClient, db: Session) -> None:
    staff = make_user(db, UserRole.OPERATIONS_MANAGER, active=False)

    response = await client.post("/api/v1/venues", headers=auth(staff), json=venue_body())

    assert response.status_code == 403


# --- TC-US20-10 tags are trimmed, de-duplicated and kept in D18 order ---


async def test_tc_us20_10_tags_are_trimmed_deduplicated_and_ordered(client: AsyncClient, db: Session) -> None:
    response = await client.post(
        "/api/v1/venues",
        headers=auth(make_staff(db)),
        json=venue_body(
            facilities=[" wifi", "projector", "wifi ", "projector"],
            accessibility_features=["lift", "wheelchair", "lift"],
            room_layouts=["theatre", "theatre"],
        ),
    )

    assert response.status_code == 201
    assert response.json()["facilities"] == ["projector", "wifi"]
    assert response.json()["accessibility_features"] == ["wheelchair", "lift"]
    assert response.json()["room_layouts"] == ["theatre"]


# --- TC-US20-11 unknown tags ---


@pytest.mark.parametrize("field", ["facilities", "accessibility_features", "room_layouts"])
async def test_tc_us20_11_unknown_tag_names_the_field_and_the_tag(
    client: AsyncClient, db: Session, field: str
) -> None:
    response = await client.post(
        "/api/v1/venues", headers=auth(make_staff(db)), json=venue_body(**{field: ["jacuzzi"]})
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_VENUE"
    assert response.json()["fields"] == [field]
    assert "jacuzzi" in response.json()["errors"][field]


# --- TC-US20-12 missing required fields on create ---


async def test_tc_us20_12_create_without_required_fields_lists_them(client: AsyncClient, db: Session) -> None:
    body = venue_body()
    del body["name"]
    del body["capacity"]

    response = await client.post("/api/v1/venues", headers=auth(make_staff(db)), json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "MISSING_REQUIRED_FIELD"
    assert response.json()["fields"] == ["name", "capacity"]


# --- TC-US20-13 PATCH validates the merged venue ---


async def test_tc_us20_13_patch_checks_hours_against_the_stored_value(client: AsyncClient, db: Session) -> None:
    venue = make_venue(db)  # 08:00 to 20:00

    response = await client.patch(
        f"/api/v1/venues/{venue.id}", headers=auth(make_staff(db)), json={"opens_at": "21:00"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_VENUE"
    assert response.json()["fields"] == ["closes_at"]


async def test_tc_us20_13_patch_cannot_null_a_required_field(client: AsyncClient, db: Session) -> None:
    venue = make_venue(db)

    response = await client.patch(
        f"/api/v1/venues/{venue.id}", headers=auth(make_staff(db)), json={"capacity": None}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "MISSING_REQUIRED_FIELD"
    assert response.json()["fields"] == ["capacity"]


# --- TC-US20-14 who sees inactive venues ---


async def test_tc_us20_14_staff_can_list_inactive_venues(client: AsyncClient, db: Session) -> None:
    make_venue(db, name="Active Room")
    inactive = make_venue(db, name="Closed Room", is_active=False)
    staff = make_staff(db)

    every = names(await client.get("/api/v1/venues", headers=auth(staff)))
    only_inactive = names(await client.get("/api/v1/venues?active=false", headers=auth(staff)))
    only_active = names(await client.get("/api/v1/venues?active=true", headers=auth(staff)))

    assert {"Active Room", "Closed Room"} <= set(every)
    assert "Closed Room" in only_inactive and "Active Room" not in only_inactive
    assert "Active Room" in only_active and "Closed Room" not in only_active
    assert (await client.get(f"/api/v1/venues/{inactive.id}", headers=auth(staff))).status_code == 200


async def test_tc_us20_14_other_roles_never_see_inactive_venues(client: AsyncClient, db: Session) -> None:
    make_venue(db, name="Closed Room", is_active=False)
    organiser = make_user(db, UserRole.ORGANISER)

    for query in ("", "?active=false"):
        assert "Closed Room" not in names(await client.get(f"/api/v1/venues{query}", headers=auth(organiser)))


# --- TC-US20-15 identity required ---


async def test_tc_us20_15_every_route_needs_an_identity(client: AsyncClient, db: Session) -> None:
    venue = make_venue(db)

    responses = [
        await client.get("/api/v1/venues"),
        await client.get(f"/api/v1/venues/{venue.id}"),
        await client.post("/api/v1/venues", json=venue_body()),
        await client.patch(f"/api/v1/venues/{venue.id}", json={"capacity": 99}),
        await client.post(f"/api/v1/venues/{venue.id}/deactivate"),
        await client.post(f"/api/v1/venues/{venue.id}/reactivate"),
    ]

    assert [r.status_code for r in responses] == [401] * 6
    assert all(r.json()["code"] == "UNAUTHENTICATED" for r in responses)


# --- TC-US20-16 list search and filters ---


async def test_tc_us20_16_search_by_part_of_a_name_ignoring_case(client: AsyncClient, db: Session) -> None:
    make_venue(db, name="Zeta Lecture Theatre")
    make_venue(db, name="Zeta Boardroom")
    make_venue(db, name="Unrelated Hall")
    reader = make_user(db, UserRole.COORDINATOR)

    found = names(await client.get("/api/v1/venues?q=zeta", headers=auth(reader)))

    assert found == ["Zeta Boardroom", "Zeta Lecture Theatre"]


async def test_tc_us20_16_filters_by_capacity_and_all_given_tags(client: AsyncClient, db: Session) -> None:
    make_venue(db, name="Qx Small", capacity=10, facilities=["projector", "wifi"], accessibility_features=["lift"])
    make_venue(db, name="Qx Big Both", capacity=200, facilities=["projector", "wifi"], accessibility_features=["lift"])
    make_venue(db, name="Qx Big Projector", capacity=200, facilities=["projector"], accessibility_features=["lift"])
    make_venue(db, name="Qx Big No Lift", capacity=200, facilities=["projector", "wifi"])
    reader = make_user(db, UserRole.ORGANISER)

    response = await client.get(
        "/api/v1/venues?q=qx&min_capacity=100&facilities=projector&facilities=wifi&accessibility=lift",
        headers=auth(reader),
    )

    assert response.status_code == 200
    assert names(response) == ["Qx Big Both"]


async def test_tc_us20_16_unknown_filter_tag_is_rejected(client: AsyncClient, db: Session) -> None:
    response = await client.get("/api/v1/venues?facilities=jacuzzi", headers=auth(make_staff(db)))

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_VENUE"
    assert response.json()["fields"] == ["facilities"]


# --- TC-US20-17 the buffer lock without bookings (US22's TC-US22-03 covers it with bookings) ---


def test_tc_us20_17_a_venue_without_bookings_is_never_locked(db: Session) -> None:
    venue = make_venue(db)

    assert venue_service_module.has_approved_future_bookings(db, venue.id, NOW) is False


async def test_tc_us20_17_buffer_edits_pass_today(client: AsyncClient, db: Session) -> None:
    venue = make_venue(db)

    response = await client.patch(
        f"/api/v1/venues/{venue.id}", headers=auth(make_staff(db)), json={"setup_minutes": 0, "turnaround_minutes": 5}
    )

    assert response.status_code == 200
    assert response.json()["setup_minutes"] == 0
    assert response.json()["turnaround_minutes"] == 5


async def test_tc_us20_17_unchanged_buffer_values_are_not_an_edit(
    client: AsyncClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    venue = make_venue(db)  # 30 / 15
    lock_buffers(monkeypatch)

    response = await client.patch(
        f"/api/v1/venues/{venue.id}",
        headers=auth(make_staff(db)),
        json={"name": "Form Resubmit", "setup_minutes": 30, "turnaround_minutes": 15},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Form Resubmit"


# --- TC-US20-18 unknown ids and fields ---


async def test_tc_us20_18_unknown_venue_is_not_found(client: AsyncClient, db: Session) -> None:
    staff = make_staff(db)
    missing = uuid.uuid4()

    responses = [
        await client.get(f"/api/v1/venues/{missing}", headers=auth(staff)),
        await client.patch(f"/api/v1/venues/{missing}", headers=auth(staff), json={"capacity": 5}),
        await client.post(f"/api/v1/venues/{missing}/deactivate", headers=auth(staff)),
        await client.post(f"/api/v1/venues/{missing}/reactivate", headers=auth(staff)),
    ]

    assert [r.status_code for r in responses] == [404] * 4
    assert all(r.json()["code"] == "NOT_FOUND" for r in responses)


async def test_tc_us20_18_unknown_body_field_is_rejected(client: AsyncClient, db: Session) -> None:
    response = await client.post(
        "/api/v1/venues", headers=auth(make_staff(db)), json=venue_body(is_active=False, colour="red")
    )

    assert response.status_code == 422
