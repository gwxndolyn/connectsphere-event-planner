import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.event.models import ChangeRequestStatus, DeliveryMode, EventStatus
from app.event.request_schemas import CoordinatorOut


class EventEditWrite(BaseModel):
    """US12 (SCRUM-15) edit body: only the fields sent are changed. Values arrive unchecked so the service
    can name every invalid field at once (`INVALID_EVENT_EDIT`, AC 4) instead of FastAPI's generic 422.
    Anything else, such as `status` or `venue_name` (venues are booked through US22), is refused."""

    model_config = ConfigDict(extra="forbid")

    name: Any = None
    event_category: Any = None
    purpose: Any = None
    room_layout_preference: Any = None
    accessibility_needs: Any = None
    equipment_needs: Any = None
    join_link: Any = None
    start_at: Any = None
    end_at: Any = None
    capacity: Any = None
    expected_attendees: Any = None
    delivery_mode: Any = None


class FieldChangeOut(BaseModel):
    field: str
    old_value: Any
    new_value: Any


class ChangeRequestOut(BaseModel):
    id: uuid.UUID
    status: ChangeRequestStatus
    changes: list[FieldChangeOut]
    requested_by: CoordinatorOut
    created_at: datetime


class CoordinatedEventOut(BaseModel):
    """An event the caller coordinates, past the request stage. `editable` is AC 1: true only in planning."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: EventStatus
    editable: bool
    start_at: datetime
    end_at: datetime


class CoordinatedEventsOut(BaseModel):
    events: list[CoordinatedEventOut]


class EventDetailsOut(CoordinatedEventOut):
    request_reference: str | None
    event_category: str | None
    purpose: str | None
    room_layout_preference: str | None
    accessibility_needs: str | None
    equipment_needs: str | None
    join_link: str | None
    capacity: int
    expected_attendees: int | None
    delivery_mode: DeliveryMode
    venue_name: str | None
    room_number: str | None
    pending_change_requests: list[ChangeRequestOut]


class EventEditOut(BaseModel):
    """`saved`: the event changed (AC 2). `pending_approval`: it didn't, and `change_request` holds the edit (AC 3)."""

    outcome: Literal["saved", "pending_approval"]
    message: str
    event: EventDetailsOut
    change_request: ChangeRequestOut | None


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    field: str
    previous_value: Any
    new_value: Any
    user: CoordinatorOut
    created_at: datetime
    # Set when the entry belongs to a critical edit, which the event doesn't show until it's approved.
    change_request_id: uuid.UUID | None
    change_request_status: ChangeRequestStatus | None


class EventHistoryOut(BaseModel):
    entries: list[AuditEntryOut]
