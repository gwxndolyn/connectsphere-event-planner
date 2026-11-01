import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.agenda.models import SessionType


class SessionWrite(BaseModel):
    """A session to add, or the fields of one to change (only those sent change). Optional, and the type a
    plain string, so the service names every invalid field at once (US15 AC 2). Unknown fields are refused."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    session_type: str | None = None
    speaker_name: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    title: str
    session_type: SessionType
    speaker_name: str | None
    starts_at: datetime
    ends_at: datetime
    # D94: the event's window can move after a session is saved (as D65), so the Agenda marks it.
    outside_window: bool


class SessionsOut(BaseModel):
    sessions: list[SessionOut]
