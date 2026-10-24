"""US26 equipment requests, PR 2 (SCRUM-109, story SCRUM-94): the seeded event the equipment screens
(SCRUM-110, TC-US26-16) add lines to. See docs/testing/US26-equipment-requests.md."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.equipment.models import EquipmentRequestLine
from app.event.models import Event, EventStatus
from app.seed import EQUIPMENT_EVENT, seed, seed_id
from app.user.models import User
from tests.factories import NOW


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
