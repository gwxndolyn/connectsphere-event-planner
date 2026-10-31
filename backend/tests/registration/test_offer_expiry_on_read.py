"""SCRUM-137 (D1, D2): a lapsed waitlist offer expires on the next read or change of its event's
registrations, and the place passes to the next person in line, or back to capacity."""

import threading
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

import app.registration.service as registration_module
from app.event.models import Event
from app.registration.models import AttendanceLog, Registration, RegistrationStatus
from app.registration.service import WAITLIST_OFFER_WINDOW, registration_service
from app.user.models import Attendee, User, UserRole
from tests.conftest import FakeNotifier
from tests.factories import NOW, make_attendee, make_event, make_registration, make_user

pytestmark = pytest.mark.anyio

LAPSED = NOW - timedelta(minutes=1)


def attendee_auth(attendee: Attendee) -> dict[str, str]:
    return {"X-Attendee-Id": str(attendee.id)}


def user_auth(user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id)}


class Lapsed:
    """An event whose seat B was offered, and B let the window pass. C is next in the queue."""

    def __init__(self, db: Session, *, capacity: int = 1, waiting: bool = True, **event_overrides) -> None:
        self.organiser = make_user(db, UserRole.ORGANISER)
        self.event = make_event(db, capacity=capacity, start_at=NOW + timedelta(days=1), **event_overrides)
        self.event.created_by_user_id = self.organiser.id
        make_registration(db, self.event, make_attendee(db), status=RegistrationStatus.WITHDRAWN)
        self.b_attendee = make_attendee(db)
        self.b = make_registration(
            db,
            self.event,
            self.b_attendee,
            status=RegistrationStatus.OFFERED,
            waitlist_joined_at=NOW - timedelta(hours=30),
            offer_expires_at=LAPSED,
        )
        self.c_attendee = make_attendee(db)
        self.c = (
            make_registration(
                db,
                self.event,
                self.c_attendee,
                status=RegistrationStatus.WAITLISTED,
                waitlist_joined_at=NOW - timedelta(hours=29),
            )
            if waiting
            else None
        )
        db.flush()


def actions(db: Session, registration: Registration) -> list[str]:
    return list(
        db.scalars(
            select(AttendanceLog.action)
            .where(AttendanceLog.registration_id == registration.id)
            .order_by(AttendanceLog.occurred_at, AttendanceLog.id)
        )
    )


def assert_passed_to_c(db: Session, notifier: FakeNotifier, lapsed: Lapsed) -> None:
    db.expire_all()
    assert lapsed.b.status == RegistrationStatus.EXPIRED
    assert actions(db, lapsed.b) == ["offer_expired"]
    assert lapsed.c is not None
    assert lapsed.c.status == RegistrationStatus.OFFERED
    assert lapsed.c.offer_expires_at == NOW + WAITLIST_OFFER_WINDOW
    assert actions(db, lapsed.c) == ["offered"]
    assert [offer["registration_id"] for offer in notifier.offers] == [lapsed.c.id]


# --- TC-US7-16 any read or change of the event's registrations passes a lapsed offer on ---


async def read_board(client: AsyncClient, db: Session, lapsed: Lapsed):
    return await client.get("/api/v1/events/available", headers=attendee_auth(make_attendee(db)))


async def read_my_events(client: AsyncClient, db: Session, lapsed: Lapsed):
    return await client.get("/api/v1/me/registrations", headers=attendee_auth(lapsed.c_attendee))


async def read_organiser_list(client: AsyncClient, db: Session, lapsed: Lapsed):
    return await client.get(f"/api/v1/events/{lapsed.event.id}/registrations", headers=user_auth(lapsed.organiser))


async def register_someone_else(client: AsyncClient, db: Session, lapsed: Lapsed):
    return await client.post(
        f"/api/v1/events/{lapsed.event.id}/registrations",
        json={"answers": {}},
        headers=attendee_auth(make_attendee(db)),
    )


async def join_someone_else(client: AsyncClient, db: Session, lapsed: Lapsed):
    return await client.post(f"/api/v1/events/{lapsed.event.id}/waitlist", headers=attendee_auth(make_attendee(db)))


async def b_accepts(client: AsyncClient, db: Session, lapsed: Lapsed):
    return await client.post(f"/api/v1/registrations/{lapsed.b.id}/accept", headers=attendee_auth(lapsed.b_attendee))


async def b_declines(client: AsyncClient, db: Session, lapsed: Lapsed):
    return await client.post(f"/api/v1/registrations/{lapsed.b.id}/decline", headers=attendee_auth(lapsed.b_attendee))


@pytest.mark.parametrize(
    ("read_or_change", "expected_status"),
    [
        (read_board, 200),
        (read_my_events, 200),
        (read_organiser_list, 200),
        (register_someone_else, 409),
        (join_someone_else, 201),
        (b_accepts, 409),
        (b_declines, 409),
    ],
    ids=["board", "my-events", "organiser-list", "register", "join-waitlist", "accept", "decline"],
)
async def test_tc_us7_16_a_lapsed_offer_passes_to_the_next_person_on_any_read_or_change(
    client: AsyncClient, db: Session, notifier: FakeNotifier, read_or_change, expected_status: int
) -> None:
    lapsed = Lapsed(db)

    response = await read_or_change(client, db, lapsed)

    assert response.status_code == expected_status
    assert_passed_to_c(db, notifier, lapsed)


async def test_tc_us7_16_withdrawing_from_the_event_passes_a_lapsed_offer_on(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    """Capacity 2, so D can hold a confirmed seat beside B's offer. Before D's withdrawal does its own
    work, B's lapsed seat goes to C. D's freed seat then has no one left waiting, so it's simply free."""
    lapsed = Lapsed(db, capacity=2)
    d_attendee = make_attendee(db)
    d = make_registration(db, lapsed.event, d_attendee)

    response = await client.post(f"/api/v1/registrations/{d.id}/withdraw", headers=attendee_auth(d_attendee))

    assert response.status_code == 200
    assert response.json()["seats_remaining"] == 1
    assert_passed_to_c(db, notifier, lapsed)


async def test_tc_us7_16_a_live_offer_is_left_alone_without_taking_a_lock(
    client: AsyncClient, db: Session, notifier: FakeNotifier, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cheap path: a board read with no lapsed offer locks nothing and writes nothing."""
    lapsed = Lapsed(db)
    lapsed.b.offer_expires_at = NOW + timedelta(hours=1)
    db.flush()
    locked: list[uuid.UUID] = []
    original = registration_module._lock_event
    monkeypatch.setattr(
        registration_module, "_lock_event", lambda db, event_id: locked.append(event_id) or original(db, event_id)
    )

    response = await read_board(client, db, lapsed)

    assert response.status_code == 200
    assert locked == []
    db.expire_all()
    assert lapsed.b.status == RegistrationStatus.OFFERED
    assert lapsed.c is not None and lapsed.c.status == RegistrationStatus.WAITLISTED
    assert actions(db, lapsed.b) == [] and actions(db, lapsed.c) == []
    assert notifier.offers == []


# --- TC-US7-17 accepting a lapsed offer is still refused, and the place still moves on ---


async def test_tc_us7_17_accepting_a_lapsed_offer_is_refused_and_the_place_moves_on(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    lapsed = Lapsed(db)

    response = await b_accepts(client, db, lapsed)

    assert response.status_code == 409
    assert response.json() == {"code": "OFFER_EXPIRED"}
    # The sweep committed before accept refused, so the 409 doesn't undo the hand-over.
    assert_passed_to_c(db, notifier, lapsed)


async def test_tc_us7_17_an_offer_already_swept_is_still_offer_expired(
    client: AsyncClient, db: Session
) -> None:
    lapsed = Lapsed(db)
    await read_board(client, db, lapsed)

    response = await b_accepts(client, db, lapsed)

    assert response.status_code == 409
    assert response.json() == {"code": "OFFER_EXPIRED"}


# --- TC-US7-18 nobody waiting: the seat returns to capacity ---


async def test_tc_us7_18_with_nobody_waiting_the_seat_returns_to_capacity(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    lapsed = Lapsed(db, waiting=False)

    response = await read_board(client, db, lapsed)

    board = {event["id"]: event for event in response.json()["events"]}
    assert board[str(lapsed.event.id)]["seats_remaining"] == 1
    assert board[str(lapsed.event.id)]["is_full"] is False
    db.expire_all()
    assert lapsed.b.status == RegistrationStatus.EXPIRED
    assert actions(db, lapsed.b) == ["offer_expired"]
    assert notifier.offers == []


# --- TC-US7-19 two requests at the same moment offer the seat once ---


class Committed:
    """Rows committed for real, so two sessions on separate connections both see them."""

    def __init__(self, event_id: uuid.UUID, b_id: uuid.UUID, c_id: uuid.UUID, user_ids: list[uuid.UUID]) -> None:
        self.event_id, self.b_id, self.c_id, self.user_ids = event_id, b_id, c_id, user_ids

    def sweep(self, engine: Engine, notifier: FakeNotifier) -> int:
        with Session(engine) as session:
            return registration_service.expire_lapsed_offers(session, [self.event_id], NOW, notifier)


@pytest.fixture
def committed(engine: Engine) -> Generator[Committed, None, None]:
    """The `db` fixture's rows are in one uncommitted transaction, invisible to other connections, so
    this commits its own and deletes them afterwards (as TC-US14-13 does)."""
    with Session(engine) as setup:
        event = make_event(setup, capacity=1, start_at=NOW + timedelta(days=1))
        b_attendee, c_attendee = make_attendee(setup), make_attendee(setup)
        b = make_registration(
            setup,
            event,
            b_attendee,
            status=RegistrationStatus.OFFERED,
            waitlist_joined_at=NOW - timedelta(hours=30),
            offer_expires_at=LAPSED,
        )
        c = make_registration(
            setup, event, c_attendee, status=RegistrationStatus.WAITLISTED, waitlist_joined_at=NOW - timedelta(hours=29)
        )
        setup.commit()
        rows = Committed(event.id, b.id, c.id, [b_attendee.id, c_attendee.id])
    try:
        yield rows
    finally:
        with Session(engine) as cleanup:
            cleanup.execute(delete(AttendanceLog).where(AttendanceLog.event_id == rows.event_id))
            cleanup.execute(delete(Registration).where(Registration.event_id == rows.event_id))
            cleanup.execute(delete(Event).where(Event.id == rows.event_id))
            cleanup.execute(delete(Attendee).where(Attendee.id.in_(rows.user_ids)))
            cleanup.execute(delete(User).where(User.id.in_(rows.user_ids)))
            cleanup.commit()


def test_tc_us7_19_two_sweeps_at_the_same_moment_offer_the_seat_once(
    engine: Engine, committed: Committed, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real race: both sessions have seen the lapsed offer without a lock and wait at a barrier just
    before locking the event, then both go. The second waits for the first's commit, re-checks under the
    lock and finds nothing left to expire, so C is offered the seat once. Without the re-check, twice."""
    barrier = threading.Barrier(2, timeout=10)
    original = registration_module._lock_event

    def wait_then_lock(db: Session, event_id: uuid.UUID) -> Event:
        barrier.wait()
        return original(db, event_id)

    monkeypatch.setattr(registration_module, "_lock_event", wait_then_lock)
    notifier = FakeNotifier()
    outcomes: list[int] = []
    threads = [threading.Thread(target=lambda: outcomes.append(committed.sweep(engine, notifier))) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes) == [0, 1]
    with Session(engine) as check:
        assert check.get(Registration, committed.b_id).status == RegistrationStatus.EXPIRED
        assert check.get(Registration, committed.c_id).status == RegistrationStatus.OFFERED

        def logged(registration_id: uuid.UUID, action: str) -> int:
            return check.scalar(
                select(func.count()).where(
                    AttendanceLog.registration_id == registration_id, AttendanceLog.action == action
                )
            )

        assert logged(committed.b_id, "offer_expired") == 1
        assert logged(committed.c_id, "offered") == 1
    assert [offer["registration_id"] for offer in notifier.offers] == [committed.c_id]


# --- TC-US7-20 a newcomer can't take a lapsed seat ahead of the waitlist ---


async def test_tc_us7_20_a_newcomer_gets_event_full_and_the_head_is_offered_the_seat(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    lapsed = Lapsed(db)
    newcomer = make_attendee(db)

    response = await client.post(
        f"/api/v1/events/{lapsed.event.id}/registrations", json={"answers": {}}, headers=attendee_auth(newcomer)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EVENT_FULL"
    assert response.json()["waitlist_available"] is True
    assert_passed_to_c(db, notifier, lapsed)
    assert db.scalars(select(Registration).where(Registration.attendee_id == newcomer.id)).first() is None


# --- TC-US7-21 declining a lapsed offer ---


async def test_tc_us7_21_declining_a_lapsed_offer_is_offer_expired(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    lapsed = Lapsed(db)

    response = await b_declines(client, db, lapsed)

    assert response.status_code == 409
    assert response.json() == {"code": "OFFER_EXPIRED"}
    # Expired, not declined: the window had passed before B answered.
    assert_passed_to_c(db, notifier, lapsed)


# --- TC-US7-22 the holder sees the offer as expired ---


async def test_tc_us7_22_the_holder_sees_the_expired_offer_in_my_events(client: AsyncClient, db: Session) -> None:
    lapsed = Lapsed(db)

    body = (await client.get("/api/v1/me/registrations", headers=attendee_auth(lapsed.b_attendee))).json()

    assert body["offered"] == [] and body["waitlisted"] == [] and body["confirmed"] == []
    [row] = body["expired"]
    assert row["registration_id"] == str(lapsed.b.id)
    assert row["event_id"] == str(lapsed.event.id)
    assert row["event_name"] == lapsed.event.name
    assert datetime.fromisoformat(row["offer_expires_at"]) == LAPSED


async def test_tc_us7_22_the_expired_row_goes_once_the_holder_rejoins_the_queue(
    client: AsyncClient, db: Session
) -> None:
    lapsed = Lapsed(db)
    joined = await client.post(
        f"/api/v1/events/{lapsed.event.id}/waitlist", headers=attendee_auth(lapsed.b_attendee)
    )
    assert joined.status_code == 201

    body = (await client.get("/api/v1/me/registrations", headers=attendee_auth(lapsed.b_attendee))).json()

    assert body["expired"] == []
    assert [row["event_id"] for row in body["waitlisted"]] == [str(lapsed.event.id)]


async def test_tc_us7_22_a_forced_early_expiry_shows_when_it_ended(client: AsyncClient, db: Session) -> None:
    """`/expire-offer` (tests only) can end an offer before its window; the row shows the real end."""
    lapsed = Lapsed(db)
    lapsed.b.offer_expires_at = NOW + timedelta(hours=5)
    db.flush()
    await client.post(f"/api/v1/registrations/{lapsed.b.id}/expire-offer", headers=attendee_auth(lapsed.b_attendee))

    body = (await client.get("/api/v1/me/registrations", headers=attendee_auth(lapsed.b_attendee))).json()

    assert [datetime.fromisoformat(row["offer_expires_at"]) for row in body["expired"]] == [NOW]


# --- TC-US7-23 once the event has started, a lapsed offer expires but isn't passed on ---


async def test_tc_us7_23_a_started_event_expires_the_offer_without_offering_the_place(
    client: AsyncClient, db: Session, notifier: FakeNotifier
) -> None:
    lapsed = Lapsed(db)
    lapsed.event.start_at = NOW - timedelta(minutes=30)
    lapsed.event.end_at = NOW + timedelta(hours=1)
    db.flush()

    response = await read_organiser_list(client, db, lapsed)

    assert response.status_code == 200
    db.expire_all()
    assert lapsed.b.status == RegistrationStatus.EXPIRED
    assert actions(db, lapsed.b) == ["offer_expired"]
    assert lapsed.c is not None and lapsed.c.status == RegistrationStatus.WAITLISTED
    assert actions(db, lapsed.c) == []
    assert notifier.offers == []


# --- TC-US7-24 several events on one board are swept one transaction at a time, in id order ---


async def test_tc_us7_24_each_event_is_swept_in_its_own_transaction_in_id_order(
    client: AsyncClient, db: Session, notifier: FakeNotifier, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = Lapsed(db), Lapsed(db)
    calls: list[tuple[str, uuid.UUID | None]] = []
    original_lock = registration_module._lock_event
    original_commit = db.commit

    def lock(session: Session, event_id: uuid.UUID) -> Event:
        calls.append(("lock", event_id))
        return original_lock(session, event_id)

    def commit() -> None:
        calls.append(("commit", None))
        original_commit()

    monkeypatch.setattr(registration_module, "_lock_event", lock)
    monkeypatch.setattr(db, "commit", commit)

    response = await read_board(client, db, first)

    assert response.status_code == 200
    ordered = sorted([first.event.id, second.event.id])
    # Lock one event, commit (releasing it), then the next: never two event locks at once.
    assert calls == [("lock", ordered[0]), ("commit", None), ("lock", ordered[1]), ("commit", None)]
    db.expire_all()
    for lapsed in (first, second):
        assert lapsed.b.status == RegistrationStatus.EXPIRED
        assert lapsed.c is not None and lapsed.c.status == RegistrationStatus.OFFERED
    assert len(notifier.offers) == 2
