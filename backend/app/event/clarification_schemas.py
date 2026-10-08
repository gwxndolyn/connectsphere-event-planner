import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.event.models import ClarificationKind, EventStatus


class ClarificationRequestWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Plain strings, checked in the service, so an unknown section comes back as a
    # coded INVALID_CLARIFICATION rather than FastAPI's generic validation error.
    sections: list[str] = []
    comment: str = ""


class ClarificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    round: int
    kind: ClarificationKind
    sections: list[str] | None
    comment: str
    author_user_id: uuid.UUID
    created_at: datetime


class ClarificationThreadOut(BaseModel):
    clarifications: list[ClarificationOut]


class ClarificationSentOut(BaseModel):
    clarification: ClarificationOut
    status: EventStatus  # the request's new status: awaiting_clarification
