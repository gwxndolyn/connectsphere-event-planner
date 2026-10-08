import uuid
from datetime import timedelta

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.clarification_schemas import ClarificationRequestWrite
from app.event.clarification_service import clarification_service
from app.event.models import (
    ClarificationKind,
    Event,
    EventRequestClarification,
    EventStatus,
)
from app.seed import seed, seed_id
from app.user.models import User, UserRole
from tests.factories import NOW


def make_user(db: Session, role: UserRole) -> User:
    user = User(email=f"{uuid.uuid4().hex}@smu.edu.sg", role=role)
    db.add(user)
    db.flush()
    return user


def make_submitted_request(db: Session, organiser: User) -> Event:
    event = Event(
        name="Community design workshop",
        status=EventStatus.SUBMITTED,
        registration_enabled=False,
        created_by_user_id=organiser.id,
        submitted_by_user_id=organiser.id,
        submitted_at=NOW - timedelta(days=1),
        request_reference=f"ER-2026-{uuid.uuid4().int % 1_000_000:06d}",
    )
    db.add(event)
    db.flush()
    return event


def ask(sections: list[str], comment: str = "Please confirm the expected headcount.") -> ClarificationRequestWrite:
    return ClarificationRequestWrite(sections=sections, comment=comment)


def domain_error(db: Session, event: Event, coordinator: User, body: ClarificationRequestWrite) -> DomainError:
    with pytest.raises(DomainError) as raised:
        clarification_service.add_request(db, event, coordinator, body, NOW)
    return raised.value


@pytest.fixture
def organiser(db: Session) -> User:
    return make_user(db, UserRole.ORGANISER)


@pytest.fixture
def coordinator(db: Session) -> User:
    return make_user(db, UserRole.COORDINATOR)


@pytest.fixture
def request_event(db: Session, organiser: User) -> Event:
    return make_submitted_request(db, organiser)


def test_tc_us8_01_clarification_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)

    assert inspector.has_table("event_request_clarifications")
    columns = {column["name"] for column in inspector.get_columns("event_request_clarifications")}
    assert {"id", "event_id", "round", "kind", "sections", "comment", "author_user_id", "created_at"} <= columns
    assert any(
        constraint["column_names"] == ["event_id", "round", "kind"]
        for constraint in inspector.get_unique_constraints("event_request_clarifications")
    )
    assert db.execute(
        text("select relrowsecurity from pg_class where oid = 'event_request_clarifications'::regclass")
    ).scalar_one() is True


def test_tc_us8_02_records_sections_comment_author_and_time(
    db: Session, request_event: Event, coordinator: User
) -> None:
    saved = clarification_service.add_request(
        db, request_event, coordinator, ask(["equipment", "attendance"], "  How many mics?  "), NOW
    )

    assert saved.round == 1
    assert saved.kind == ClarificationKind.REQUEST
    assert saved.sections == ["attendance", "equipment"]  # canonical order, not the order sent
    assert saved.comment == "How many mics?"
    assert saved.author_user_id == coordinator.id
    assert saved.created_at == NOW
    stored = db.get(EventRequestClarification, saved.id)
    assert stored is not None and stored.event_id == request_event.id


def test_tc_us8_03_requires_a_section_and_a_comment(
    db: Session, request_event: Event, coordinator: User
) -> None:
    error = domain_error(db, request_event, coordinator, ask([], "   "))

    assert error.status_code == 422
    assert error.code == "MISSING_REQUIRED_FIELD"
    assert error.extra["fields"] == ["sections", "comment"]


def test_tc_us8_04_rejects_unknown_or_repeated_sections(
    db: Session, request_event: Event, coordinator: User
) -> None:
    unknown = domain_error(db, request_event, coordinator, ask(["attendance", "catering"]))
    repeated = domain_error(db, request_event, coordinator, ask(["layout", "layout"]))

    assert unknown.code == repeated.code == "INVALID_CLARIFICATION"
    assert unknown.extra == {"fields": ["sections"], "sections": ["catering"]}
    assert repeated.extra["fields"] == ["sections"]
    assert clarification_service.list_thread(db, request_event.id) == []


def test_tc_us8_05_later_requests_open_new_rounds(
    db: Session, request_event: Event, coordinator: User
) -> None:
    first = clarification_service.add_request(db, request_event, coordinator, ask(["schedule"]), NOW)
    second = clarification_service.add_request(
        db, request_event, coordinator, ask(["layout"]), NOW + timedelta(hours=1)
    )
    other_event = make_submitted_request(db, make_user(db, UserRole.ORGANISER))
    other = clarification_service.add_request(db, other_event, coordinator, ask(["details"]), NOW)

    assert (first.round, second.round, other.round) == (1, 2, 1)


def test_tc_us8_06_thread_lists_rounds_with_replies_in_order(
    db: Session, request_event: Event, organiser: User, coordinator: User
) -> None:
    clarification_service.add_request(db, request_event, coordinator, ask(["attendance"]), NOW)
    # A reply as SCRUM-77 will store it; inserted directly until that endpoint exists.
    db.add(
        EventRequestClarification(
            event_id=request_event.id,
            round=1,
            kind=ClarificationKind.RESPONSE,
            sections=None,
            comment="About 30 people.",
            author_user_id=organiser.id,
            created_at=NOW + timedelta(hours=2),
        )
    )
    db.flush()
    clarification_service.add_request(
        db, request_event, coordinator, ask(["layout"]), NOW + timedelta(hours=3)
    )

    thread = clarification_service.list_thread(db, request_event.id)

    assert [(message.round, message.kind) for message in thread] == [
        (1, ClarificationKind.REQUEST),
        (1, ClarificationKind.RESPONSE),
        (2, ClarificationKind.REQUEST),
    ]


@pytest.mark.parametrize(
    ("kind", "sections", "comment"),
    [
        (ClarificationKind.REQUEST, [], "No section tagged"),
        (ClarificationKind.REQUEST, ["catering"], "Unknown section"),
        (ClarificationKind.REQUEST, ["layout"], "   "),
        (ClarificationKind.RESPONSE, ["layout"], "A reply tagging sections"),
    ],
)
def test_tc_us8_07_database_rejects_invalid_messages(
    db: Session,
    request_event: Event,
    coordinator: User,
    kind: ClarificationKind,
    sections: list[str],
    comment: str,
) -> None:
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(
                EventRequestClarification(
                    event_id=request_event.id,
                    round=1,
                    kind=kind,
                    sections=sections,
                    comment=comment,
                    author_user_id=coordinator.id,
                )
            )
            db.flush()


def test_tc_us8_07_database_allows_one_question_per_round(
    db: Session, request_event: Event, coordinator: User
) -> None:
    clarification_service.add_request(db, request_event, coordinator, ask(["schedule"]), NOW)

    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(
                EventRequestClarification(
                    event_id=request_event.id,
                    round=1,
                    kind=ClarificationKind.REQUEST,
                    sections=["layout"],
                    comment="A second question in the same round",
                    author_user_id=coordinator.id,
                )
            )
            db.flush()


def test_tc_us8_08_seed_creates_an_active_coordinator(db: Session) -> None:
    seed(db, now=NOW)

    coordinator = db.get(User, seed_id("user", "event-coordinator"))
    assert coordinator is not None
    assert coordinator.role == UserRole.COORDINATOR
    assert coordinator.is_active is True
