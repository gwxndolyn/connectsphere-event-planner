"""US15 (SCRUM-18, SCRUM-139): the Organiser builds their event's agenda, one track of sessions.

D93: the request's own Organiser changes it while the event is `draft` or `planning`; anyone who can read
the request (D11) reads it. D94: each session falls within the event's window. D95: no two overlap.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agenda.models import EventSession, SessionType
from app.agenda.schemas import SessionOut, SessionsOut, SessionWrite
from app.core.exceptions import DomainError
from app.event.models import Event, EventStatus
from app.event.request_service import event_request_service
from app.user.models import User
from app.venue.booking_service import VENUE_TIMEZONE, _schedule_errors

EDITABLE_STATUSES = (EventStatus.DRAFT, EventStatus.PLANNING)
# The body's order, so a form marks the invalid fields top to bottom.
FIELDS = ("title", "session_type", "speaker_name", "starts_at", "ends_at")
TYPES = ", ".join(session_type.value for session_type in SessionType)


def _lock_event(db: Session, event_id: uuid.UUID) -> Event | None:
    """The event FOR UPDATE: two saves to one agenda take turns, so the second sees the first's session and
    is refused as an overlap (AC 4, TC-US15-12) rather than on the exclusion constraint."""
    return db.scalars(select(Event).where(Event.id == event_id).with_for_update()).one_or_none()


def _editable_event(db: Session, organiser: User, event_id: uuid.UUID) -> Event:
    event = _lock_event(db, event_id)
    # Someone else's event is 404 (§1a), whatever its status.
    if event is None or event.created_by_user_id != organiser.id:
        raise DomainError(404, "NOT_FOUND")
    if event.status not in EDITABLE_STATUSES:
        raise DomainError(409, "AGENDA_NOT_EDITABLE", status=event.status.value)
    return event


def _window_errors(event: Event, starts_at: datetime, ends_at: datetime) -> dict[str, str]:
    """D94 (decided by the acting PO, 1 Nov): a planning event's own start_at to end_at; a draft's D65 window,
    a preferred date between the preferred times. A draft without them has no window yet."""
    if event.start_at is None and not (
        event.preferred_dates and event.preferred_start_time and event.preferred_end_time
    ):
        return {"starts_at": "Add the event's preferred dates and times before building its agenda."}
    return _schedule_errors(event, starts_at, ends_at)


def _validate(values: dict[str, Any], event: Event) -> dict[str, Any]:
    """Every field checked, each invalid one named with a message (AC 2, 3, D96). Returns them cleaned."""
    errors: dict[str, str] = {}
    title = (values["title"] or "").strip()
    if not title:
        errors["title"] = "Give the session a title."
    session_type = values["session_type"]
    if not session_type:
        errors["session_type"] = "Choose a session type."
    elif session_type not in list(SessionType):
        errors["session_type"] = f"Unknown session type: {session_type}. Allowed: {TYPES}."
    speaker_name = (values["speaker_name"] or "").strip() or None
    # D96 (decided by the acting PO, 1 Nov): every session names its speaker or presenter, except a break.
    if speaker_name is None and session_type != SessionType.BREAK:
        errors["speaker_name"] = "Name the speaker or presenter. Only a break has none."

    starts_at, ends_at = values["starts_at"], values["ends_at"]
    for field, value, label in (("starts_at", starts_at, "start"), ("ends_at", ends_at, "end")):
        if value is None:
            errors[field] = f"Give the session's {label} time."
        elif value.utcoffset() is None:
            errors[field] = "Give the time with a timezone offset, e.g. 2026-10-08T10:00:00+08:00."
    if "starts_at" not in errors and "ends_at" not in errors:
        if ends_at <= starts_at:
            errors["ends_at"] = "The end must be after the start."
        else:
            # AC 3: within the event's window (D94).
            errors |= _window_errors(event, starts_at, ends_at)

    if errors:
        ordered = {field: errors[field] for field in FIELDS if field in errors}
        raise DomainError(422, "INVALID_SESSION", fields=list(ordered), errors=ordered)
    return {
        "title": title,
        "session_type": SessionType(session_type),
        "speaker_name": speaker_name,
        "starts_at": starts_at,
        "ends_at": ends_at,
    }


def _refuse_overlap(db: Session, event: Event, values: dict[str, Any], session_id: uuid.UUID | None = None) -> None:
    """AC 4, D95: one track, so no two of the event's sessions overlap; back-to-back is fine. Asked first, so
    the refusal names the clash; `event_sessions_no_overlap` backs it up."""
    query = select(EventSession).where(
        EventSession.event_id == event.id,
        EventSession.starts_at < values["ends_at"],
        EventSession.ends_at > values["starts_at"],
    )
    if session_id is not None:
        query = query.where(EventSession.id != session_id)
    clash = db.scalars(query.order_by(EventSession.starts_at).limit(1)).first()
    if clash is not None:
        raise DomainError(
            409,
            "SESSION_OVERLAP",
            session={
                "id": str(clash.id),
                "title": clash.title,
                "starts_at": clash.starts_at.astimezone(VENUE_TIMEZONE).isoformat(),
                "ends_at": clash.ends_at.astimezone(VENUE_TIMEZONE).isoformat(),
            },
        )


def _out(session: EventSession, event: Event) -> SessionOut:
    return SessionOut(
        id=session.id,
        event_id=session.event_id,
        title=session.title,
        session_type=session.session_type,
        speaker_name=session.speaker_name,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        outside_window=bool(_window_errors(event, session.starts_at, session.ends_at)),
    )


class AgendaService:
    def list(self, db: Session, reader: User, event_id: uuid.UUID) -> SessionsOut:
        """AC 5, D97: in chronological order (start, then end, then title)."""
        event = db.get(Event, event_id)
        # D93 (decided by the acting PO, 1 Nov): whoever can read the request reads its agenda (D11, D47, D48).
        if event is None or not event_request_service._can_read(event, reader):
            raise DomainError(404, "NOT_FOUND")
        sessions = db.scalars(
            select(EventSession)
            .where(EventSession.event_id == event.id)
            .order_by(EventSession.starts_at, EventSession.ends_at, EventSession.title)
        )
        return SessionsOut(sessions=[_out(session, event) for session in sessions])

    def add(self, db: Session, organiser: User, event_id: uuid.UUID, body: SessionWrite) -> SessionOut:
        event = _editable_event(db, organiser, event_id)
        values = _validate({field: getattr(body, field) for field in FIELDS}, event)
        _refuse_overlap(db, event, values)
        session = EventSession(event_id=event.id, **values)
        db.add(session)
        db.flush()
        result = _out(session, event)
        db.commit()
        return result

    def edit(self, db: Session, organiser: User, session_id: uuid.UUID, body: SessionWrite) -> SessionOut:
        """Only the fields sent change; the session is checked whole, as if added."""
        event, session = self._editable_session(db, organiser, session_id)
        current = {field: getattr(session, field) for field in FIELDS}
        values = _validate(current | body.model_dump(exclude_unset=True), event)
        _refuse_overlap(db, event, values, session.id)
        for field, value in values.items():
            setattr(session, field, value)
        db.flush()
        result = _out(session, event)
        db.commit()
        return result

    def delete(self, db: Session, organiser: User, session_id: uuid.UUID) -> None:
        _, session = self._editable_session(db, organiser, session_id)
        db.delete(session)
        db.commit()

    def _editable_session(self, db: Session, organiser: User, session_id: uuid.UUID) -> tuple[Event, EventSession]:
        event_id = db.scalar(select(EventSession.event_id).where(EventSession.id == session_id))
        if event_id is None:
            raise DomainError(404, "NOT_FOUND")
        event = _editable_event(db, organiser, event_id)
        # Read again under the event's lock, in case another save deleted it meanwhile.
        session = db.scalars(select(EventSession).where(EventSession.id == session_id)).one_or_none()
        if session is None:
            raise DomainError(404, "NOT_FOUND")
        return event, session


agenda_service = AgendaService()
