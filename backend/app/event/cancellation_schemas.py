import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.event.models import CancellationStatus, EventStatus
from app.event.request_schemas import CoordinatorOut


class CancellationWrite(BaseModel):
    """US9 (SCRUM-12): the reason for a cancellation request, a direct cancel or a rejection (AC 1, 3; the story
    owner's choice for a rejection). Optional here so a missing reason is the API's own `MISSING_REQUIRED_FIELD`,
    like a blank one, not FastAPI's generic 422."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class CancellationOut(BaseModel):
    """AC 8: who asked and why, when, and who decided and when. A direct cancel (AC 3) has the coordinator as both."""

    id: uuid.UUID
    event_id: uuid.UUID
    event_name: str | None
    request_reference: str | None
    # The event's status after this call, so a screen can show "Cancelled" without reading the request again.
    event_status: EventStatus
    status: CancellationStatus
    reason: str
    requested_by: CoordinatorOut
    requested_at: datetime
    decided_by: CoordinatorOut | None
    decided_at: datetime | None
    rejection_reason: str | None
    # AC 3: the coordinator cancelled it themselves, rather than approving the organiser's request.
    direct: bool


class CancellationsOut(BaseModel):
    cancellations: list[CancellationOut]
