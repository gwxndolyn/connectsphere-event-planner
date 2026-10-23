import uuid

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.seed import BOOKABLE_EVENT, EVENT_COORDINATOR_LEAD_EMAILS, seed, seed_id
from app.user.models import User, UserRole
from tests.factories import make_event


def test_tc_us10a_01_coordinator_assignment_schema_is_installed(db: Session, engine) -> None:
    roles = db.execute(
        text(
            """
            select enumlabel from pg_enum
            join pg_type on pg_type.oid = pg_enum.enumtypid
            where pg_type.typname = 'user_role'
            order by enumsortorder
            """
        )
    ).scalars().all()
    assert roles == ["organiser", "coordinator", "coordinator_lead", "operations_manager", "attendee"]

    inspector = inspect(engine)
    column = {c["name"]: c for c in inspector.get_columns("events")}["coordinator_id"]
    assert column["nullable"] is True
    assert any(
        fk["constrained_columns"] == ["coordinator_id"] and fk["referred_table"] == "users"
        for fk in inspector.get_foreign_keys("events")
    )
    assert any(ix["column_names"] == ["coordinator_id"] for ix in inspector.get_indexes("events"))


def test_tc_us10a_02_new_events_are_unassigned(db: Session) -> None:
    event = make_event(db, status=EventStatus.SUBMITTED)
    assert event.coordinator_id is None


def test_tc_us10a_03_coordinator_must_be_an_existing_user(db: Session) -> None:
    event = make_event(db, status=EventStatus.SUBMITTED)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            event.coordinator_id = uuid.uuid4()
            db.flush()


def test_tc_us10a_04_seed_adds_two_active_leads_and_leaves_events_unassigned(db: Session) -> None:
    seed(db)
    seed(db)  # idempotent

    leads = db.scalars(select(User).where(User.role == UserRole.COORDINATOR_LEAD)).all()
    assert sorted(lead.email for lead in leads) == sorted(EVENT_COORDINATOR_LEAD_EMAILS)
    assert all(lead.is_active for lead in leads)
    # AC 8: organisers see a name, so the seeded coordinator and Leads have one.
    assert all(lead.full_name for lead in leads)
    assert db.scalars(select(User).where(User.role == UserRole.COORDINATOR, User.full_name.is_(None))).first() is None
    # Seeded events start unassigned, except US22's Venue Booking Demo: only its assigned coordinator
    # may book it (D20), so the seed assigns the dev coordinator for the booking screens and E2E.
    assigned = db.scalars(select(Event.id).where(Event.coordinator_id.is_not(None))).all()
    assert assigned == [seed_id("event", BOOKABLE_EVENT.slug)]
