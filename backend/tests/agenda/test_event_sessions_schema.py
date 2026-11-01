"""US15 agenda, PR 1 (SCRUM-138, story SCRUM-18): an event's sessions, each with a title, type, speaker and
times, one track per event. The API comes in SCRUM-139; see docs/testing/US15-event-agenda.md."""

import uuid
from datetime import datetime, timedelta

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agenda.models import EventSession, SessionType
from app.event.models import Event, EventStatus
from app.seed import AGENDA_EVENT_NAME, AGENDA_EVENT_SLUG, seed, seed_id
from tests.conftest import BACKEND_DIR
from tests.factories import NOW, make_event

REVISION = "20261111_1200_us15_sessions"
TEN = NOW.replace(hour=10) + timedelta(days=3)


def add_session(
    db: Session,
    event: Event,
    starts_at: datetime = TEN,
    ends_at: datetime | None = None,
    **overrides,
) -> EventSession:
    fields = {
        "event_id": event.id,
        "title": "Opening keynote",
        "session_type": SessionType.PRESENTATION,
        "speaker_name": "Dr Tan",
        "starts_at": starts_at,
        "ends_at": ends_at or starts_at + timedelta(hours=1),
    }
    session = EventSession(**(fields | overrides))
    db.add(session)
    db.flush()
    return session


def refused_on(db: Session, event: Event, **overrides) -> str:
    """The constraint a session with these fields is refused on."""
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            add_session(db, event, **overrides)
    return raised.value.orig.diag.constraint_name


def test_tc_us15_01_schema_is_installed(db: Session, engine) -> None:
    inspector = inspect(engine)

    assert {column["name"] for column in inspector.get_columns("event_sessions")} == {
        "id",
        "event_id",
        "title",
        "session_type",
        "speaker_name",
        "starts_at",
        "ends_at",
        "created_at",
        "updated_at",
    }
    types = db.scalar(text("SELECT enum_range(NULL::event_session_type)::text"))
    assert types == "{presentation,workshop,panel,break,other}"
    rls = db.scalar(text("SELECT relrowsecurity FROM pg_class WHERE oid = 'event_sessions'::regclass"))
    assert rls is True
    exclusion = db.scalar(
        text("SELECT contype FROM pg_constraint WHERE conname = 'event_sessions_no_overlap'")
    )
    assert exclusion == "x"


def test_tc_us15_01_migrations_have_one_head() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    script = ScriptDirectory.from_config(config)

    assert len(script.get_heads()) == 1
    assert REVISION in {revision.revision for revision in script.walk_revisions()}


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"title": "   "}, "event_sessions_title_not_blank"),
        ({"ends_at": TEN}, "event_sessions_window_valid"),
        ({"ends_at": TEN - timedelta(minutes=30)}, "event_sessions_window_valid"),
        ({"speaker_name": None}, "event_sessions_speaker_required"),
        ({"speaker_name": "  ", "session_type": SessionType.WORKSHOP}, "event_sessions_speaker_required"),
        ({"event_id": uuid.uuid4()}, "event_sessions_event_id_fkey"),
    ],
    ids=["blank title", "no length", "end before start", "no speaker", "blank speaker", "unknown event"],
)
def test_tc_us15_02_an_invalid_session_is_refused(db: Session, fields: dict, constraint: str) -> None:
    assert refused_on(db, make_event(db), **fields) == constraint


def test_tc_us15_02_a_break_needs_no_speaker_and_other_is_a_type(db: Session) -> None:
    event = make_event(db)

    pause = add_session(db, event, session_type=SessionType.BREAK, speaker_name=None, title="Coffee")
    qa = add_session(db, event, starts_at=TEN + timedelta(hours=1), session_type=SessionType.OTHER, title="Q&A")
    db.expire_all()

    assert (db.get(EventSession, pause.id).speaker_name, db.get(EventSession, qa.id).session_type) == (
        None,
        SessionType.OTHER,
    )


def test_tc_us15_03_one_events_sessions_never_overlap(db: Session) -> None:
    event, other = make_event(db), make_event(db)
    add_session(db, event)

    assert refused_on(db, event, starts_at=TEN + timedelta(minutes=30)) == "event_sessions_no_overlap"
    # Back-to-back fits ('[)'), and another event has its own track.
    add_session(db, event, starts_at=TEN + timedelta(hours=1))
    add_session(db, other, starts_at=TEN + timedelta(minutes=30))
    assert db.scalar(select(func.count()).where(EventSession.event_id == event.id)) == 2


def test_tc_us15_04_seed_adds_the_agenda_demo_event(db: Session) -> None:
    seed(db, now=NOW)
    demo = db.get(Event, seed_id("event", AGENDA_EVENT_SLUG))

    assert (demo.name, demo.status, demo.created_by_user_id) == (
        AGENDA_EVENT_NAME,
        EventStatus.PLANNING,
        seed_id("user", "event-organiser"),
    )
    # A whole day, so the E2E can place sessions at fixed times (TC-US15-15).
    local_start = demo.start_at.astimezone(NOW.tzinfo)
    assert (local_start.hour, local_start.minute, demo.end_at - demo.start_at) == (9, 0, timedelta(hours=8))

    count = db.scalar(select(func.count()).select_from(Event))
    seed(db, now=NOW)
    assert db.scalar(select(func.count()).select_from(Event)) == count


def test_tc_us15_04_reseed_clears_the_demo_events_sessions_only(db: Session) -> None:
    seed(db, now=NOW)
    demo = db.get(Event, seed_id("event", AGENDA_EVENT_SLUG))
    add_session(db, demo, starts_at=demo.start_at)
    other = add_session(db, make_event(db))

    seed(db, now=NOW)

    assert db.scalar(select(func.count()).where(EventSession.event_id == demo.id)) == 0
    assert db.get(EventSession, other.id) is not None
