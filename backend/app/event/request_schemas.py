import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.event.models import EventStatus


class EventRequestWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    event_category: str | None = Field(default=None, max_length=100)
    purpose: str | None = None
    preferred_dates: list[date] | None = None
    preferred_start_time: time | None = None
    preferred_end_time: time | None = None
    expected_attendees: int | None = None
    room_layout_preference: str | None = None
    accessibility_needs: str | None = None
    equipment_needs: str | None = None
    registration_required: bool | None = None


class EventRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: EventStatus
    name: str | None
    event_category: str | None
    purpose: str | None
    preferred_dates: list[date] | None
    preferred_start_time: time | None
    preferred_end_time: time | None
    expected_attendees: int | None
    room_layout_preference: str | None
    accessibility_needs: str | None
    equipment_needs: str | None
    registration_required: bool | None
    created_by_user_id: uuid.UUID | None
    submitted_by_user_id: uuid.UUID | None
    submitted_at: datetime | None
    request_reference: str | None
    created_at: datetime


class EventRequestsOut(BaseModel):
    event_requests: list[EventRequestOut]