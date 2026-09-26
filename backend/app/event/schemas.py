import uuid
from datetime import datetime

from pydantic import BaseModel

from app.event.models import DeliveryMode


class RegistrationFieldOut(BaseModel):
    field_key: str
    label: str
    field_type: str
    options: list[str] | None = None
    required: bool


class AvailableEventOut(BaseModel):
    id: uuid.UUID
    name: str
    start_at: datetime
    end_at: datetime
    delivery_mode: DeliveryMode
    venue_name: str | None = None
    join_link: str | None = None
    capacity: int
    seats_remaining: int
    is_full: bool
    already_registered: bool
    registration_fields: list[RegistrationFieldOut]


class AvailableEventsResponse(BaseModel):
    events: list[AvailableEventOut]
