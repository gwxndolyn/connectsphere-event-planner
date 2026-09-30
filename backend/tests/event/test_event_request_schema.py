import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.event.models import DeliveryMode, Event, EventStatus
from tests.factories import make_attendee


def test_tc_us1_16_request_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)
    event_status_values = db.execute(
        text(
            """
            select enumlabel
            from pg_enum
            join pg_type on pg_type.oid = pg_enum.enumtypid
            where pg_type.typname = 'event_status'
            order by enumsortorder
            """
        )
    ).scalars().all()

    assert event_status_values == [
        "draft",
        "submitted",
        "under_review",
        "awaiting_clarification",
        "approved",
        "rejected",
        "planning",
        "confirmed",
        "cancelled",
        "completed",
    ]

    event_columns = {column["name"]: column for column in inspector.get_columns("events")}
    assert event_columns["name"]["nullable"] is True
    for column_name in ("start_at", "end_at", "capacity", "delivery_mode"):
        assert event_columns[column_name]["nullable"] is True
    assert event_columns["waitlist_enabled"]["default"] in ("false", "false::boolean")
    assert {
        "event_category",
        "purpose",
        "preferred_dates",
        "preferred_start_time",
        "preferred_end_time",
        "expected_attendees",
        "room_layout_preference",
        "accessibility_needs",
        "equipment_needs",
        "registration_required",
        "created_by_user_id",
        "submitted_by_user_id",
        "submitted_at",
        "request_reference",
    } <= event_columns.keys()

    assert inspector.has_table("users")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert {"id", "email", "role", "is_active", "created_at"} <= user_columns
    assert inspector.has_sequence("event_request_reference_seq")
    assert any(
        constraint["column_names"] == ["request_reference"]
        for constraint in inspector.get_unique_constraints("events")
    )

    attendee_forekeys = inspector.get_foreign_keys("attendees")
    assert any(
        foreign_key["constrained_columns"] == ["id"]
        and foreign_key["referred_table"] == "users"
        and foreign_key["referred_columns"] == ["id"]
        for foreign_key in attendee_forekeys
    )
    assert db.execute(
        text("select relrowsecurity from pg_class where oid = 'users'::regclass")
    ).scalar_one() is True

    attendee = make_attendee(db)
    assert db.execute(
        text("select count(*) from users where id = :id and email = :email and role = 'attendee'"),
        {"id": attendee.id, "email": attendee.email},
    ).scalar_one() == 1


def test_tc_us1_16_finalized_event_rejects_null_start_at(db: Session) -> None:
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(
                Event(
                    name="Invalid confirmed event",
                    status=EventStatus.CONFIRMED,
                    registration_enabled=False,
                    start_at=None,
                    end_at=None,
                    capacity=1,
                    delivery_mode=DeliveryMode.IN_PERSON,
                )
            )
            db.flush()


def test_tc_us1_16_expected_attendees_must_be_positive(db: Session) -> None:
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(
                Event(
                    name="Draft with an invalid attendee count",
                    status=EventStatus.DRAFT,
                    registration_enabled=False,
                    start_at=None,
                    end_at=None,
                    capacity=None,
                    delivery_mode=None,
                    expected_attendees=0,
                )
            )
            db.flush()