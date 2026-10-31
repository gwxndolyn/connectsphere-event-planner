import uuid

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import Event, EventStatus
from app.seed import BOOKABLE_EVENT, EQUIPMENT_EVENT, EVENT_COORDINATOR_LEAD_EMAILS, PLANNING_EVENT, seed, seed_id
from app.seed import BOOKABLE_EVENT, EQUIPMENT_EVENT, EVENT_COORDINATOR_LEAD_EMAILS, MULTI_VENUE_EVENT, seed, seed_id
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
    # 'tech_support' is appended later by US26's migration (SCRUM-108, deviation 34), and 'venue_staff' and
    # 'safety_officer' by US16b's (SCRUM-119). 'operations_manager' stays in the type, unused (D49).
    assert roles == [
        "organiser", "coordinator", "coordinator_lead", "operations_manager", "attendee", "tech_support",
        "venue_staff", "safety_officer",
    ]

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

    leads = db.scalars(select(User).where(User.roles.any(UserRole.COORDINATOR_LEAD))).all()
    assert sorted(lead.email for lead in leads) == sorted(EVENT_COORDINATOR_LEAD_EMAILS)
    assert all(lead.is_active for lead in leads)
    # AC 8: organisers see a name, so the seeded coordinator and Leads have one.
    assert all(lead.full_name for lead in leads)
    assert db.scalars(select(User).where(User.roles.any(UserRole.COORDINATOR), User.full_name.is_(None))).first() is None
    # Seeded events start unassigned, except US22's Venue Booking Demo, US26's Equipment Request
    # Demo, US28's Intro to Supabase and US12's Event Planning Demo: only the assigned coordinator may
    # book a venue, add equipment (D20), view registrations (D52) or edit an event (US12), so the seed assigns
    # the dev coordinator to all four for their screens and E2E.
    # Demo, US28's Intro to Supabase and US24's Multi-Venue Conference Demo: only the assigned
    # coordinator may book a venue, add equipment (D20) or view registrations (D52), so the seed
    # assigns the dev coordinator to all four for their screens and E2E.
    assigned = db.scalars(select(Event.id).where(Event.coordinator_id.is_not(None))).all()
    assert sorted(assigned) == sorted(
        [
            seed_id("event", BOOKABLE_EVENT.slug),
            seed_id("event", EQUIPMENT_EVENT.slug),
            seed_id("event", "supabase-live-coding"),
            seed_id("event", PLANNING_EVENT.slug),
            seed_id("event", MULTI_VENUE_EVENT.slug),
        ]
    )
