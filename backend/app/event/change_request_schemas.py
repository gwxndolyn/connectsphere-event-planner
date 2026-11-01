import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.event.edit_schemas import FieldChangeOut
from app.event.models import ChangeRequestStatus


class ChangeRequestWrite(BaseModel):
    """US29a (SCRUM-97) body: `changes` maps each field to its proposed value (AC 1), `reason` is required (AC 3).
    Values arrive unchecked so the service names every invalid field at once (`INVALID_CHANGE_REQUEST`)."""

    model_config = ConfigDict(extra="forbid")

    changes: dict[str, Any] = {}
    reason: str | None = None


class OrganiserChangeRequestOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_name: str | None
    request_reference: str | None
    # AC 4's "Pending" is US12's pending_approval: one status for both kinds of change request.
    status: ChangeRequestStatus
    reason: str | None
    changes: list[FieldChangeOut]
    created_at: datetime


class OrganiserChangeRequestsOut(BaseModel):
    change_requests: list[OrganiserChangeRequestOut]
