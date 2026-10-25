"""US26 equipment requests, PR 2 (SCRUM-109, story SCRUM-94): the seeded event the equipment screens
(SCRUM-110, TC-US26-16) add lines to, and (PR 3, SCRUM-110) its reset on reseed. See
docs/testing/US26-equipment-requests.md."""

import sys
from contextlib import nullcontext

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.seed as seed_module
from app.core.config import settings

from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentType
from app.event.models import Event, EventStatus
from app.seed import EQUIPMENT_EVENT, seed, seed_id
from app.user.models import User
from tests.factories import NOW, make_event


def test_tc_us26_16_seed_has_a_confirmed_event_for_the_coordinator(db: Session) -> None:
    """Only planning or confirmed events take equipment lines (TC-US26-10), and only from their assigned
    coordinator (D20). No other seeded event is both, so the seed adds one for the dev coordinator."""
    seed(db, now=NOW)

    event = db.get(Event, seed_id("event", EQUIPMENT_EVENT.slug))
    assert event is not None
    assert event.name == "Equipment Request Demo"
    assert event.status == EventStatus.CONFIRMED
    assert event.start_at > NOW
    # The organiser owns it; the dev coordinator (VITE_DEV_COORDINATOR_ID) is assigned to it.
    assert db.get(User, event.created_by_user_id).email == "event.organiser@smu.edu.sg"
    assert event.coordinator_id == seed_id("user", "event-coordinator")
    # Kept off the attendees' events board, which lists confirmed events with registration enabled.
    assert event.registration_enabled is False
    assert db.scalar(select(func.count()).where(EquipmentRequestLine.event_id == event.id)) == 0


def test_tc_us26_16_reseeding_adds_no_second_event(db: Session) -> None:
    seed(db, now=NOW)
    seed(db, now=NOW)

    assert db.scalar(select(func.count()).select_from(Event).where(Event.name == "Equipment Request Demo")) == 1


def test_tc_us26_20_reseeding_clears_the_demo_events_equipment(db: Session) -> None:
    """An approved line can't be removed, and D41 allows one live line per type, so each E2E run of
    TC-US26-17 would use up a type on the demo event for good. A reseed (the rule before rerunning
    E2E, docs/testing/README.md) starts it empty again. Other events' lines are left alone."""
    seed(db, now=NOW)
    demo = db.get(Event, seed_id("event", EQUIPMENT_EVENT.slug))
    coordinator = db.get(User, seed_id("user", "event-coordinator"))
    tech = db.get(User, seed_id("user", "tech-support"))
    projector = db.get(EquipmentType, seed_id("equipment-type", "Projector"))
    laptop = db.get(EquipmentType, seed_id("equipment-type", "Laptop"))
    other_event = make_event(db, coordinator_id=coordinator.id)
    db.add_all(
        [
            EquipmentRequestLine(
                event_id=demo.id, equipment_type_id=projector.id, quantity=2, requested_by_user_id=coordinator.id
            ),
            EquipmentRequestLine(
                event_id=demo.id,
                equipment_type_id=laptop.id,
                quantity=1,
                requested_by_user_id=coordinator.id,
                status=EquipmentLineStatus.APPROVED,
                reviewed_by_user_id=tech.id,
                reviewed_at=NOW,
            ),
            EquipmentRequestLine(
                event_id=other_event.id, equipment_type_id=projector.id, quantity=1, requested_by_user_id=coordinator.id
            ),
        ]
    )
    db.flush()

    seed(db, now=NOW)

    assert db.scalar(select(func.count()).where(EquipmentRequestLine.event_id == demo.id)) == 0
    assert db.scalar(select(func.count()).where(EquipmentRequestLine.event_id == other_event.id)) == 1


def test_tc_us26_20_a_remote_reseed_says_it_empties_the_demo_events_equipment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Whoever reseeds Supabase (`--yes`) is told first that the demo event's lines go, approved ones
    included (PR #78 review). The refusal comes before any database work."""
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@db.example.supabase.co:5432/postgres")
    monkeypatch.setattr(sys, "argv", ["app.seed"])

    assert seed_module.main() == 1
    out = capsys.readouterr().out
    assert "Refusing to seed a non-local database" in out
    assert "deletes every equipment line on Equipment Request Demo, approved ones included" in out


def test_tc_us26_20_a_remote_reseed_with_yes_warns_before_it_deletes(
    db: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Whoever has already passed `--yes` sees the warning too, before anything is deleted (PR #78
    review, second round)."""
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@db.example.supabase.co:5432/postgres")
    monkeypatch.setattr(sys, "argv", ["app.seed", "--yes"])
    monkeypatch.setattr(seed_module, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(seed_module, "admin_from_settings", lambda: None)

    assert seed_module.main() == 0
    out = capsys.readouterr().out
    warning = out.index("deletes every equipment line on Equipment Request Demo, approved ones included")
    assert warning < out.index("Seeding db.example.supabase.co")
