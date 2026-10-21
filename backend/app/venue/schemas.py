import uuid
from datetime import time

from pydantic import BaseModel, ConfigDict


class VenueWrite(BaseModel):
    """Create and edit body. Every field is optional here so the service can list every missing
    field at once (`MISSING_REQUIRED_FIELD`) instead of FastAPI's generic 422; on edit, only the
    fields sent change."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    location: str | None = None
    capacity: int | None = None
    facilities: list[str] | None = None
    accessibility_features: list[str] | None = None
    room_layouts: list[str] | None = None
    opens_at: time | None = None
    closes_at: time | None = None
    setup_minutes: int | None = None
    turnaround_minutes: int | None = None


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    location: str
    capacity: int
    facilities: list[str]
    accessibility_features: list[str]
    room_layouts: list[str]
    opens_at: time
    closes_at: time
    setup_minutes: int
    turnaround_minutes: int
    is_active: bool


class VenuesOut(BaseModel):
    venues: list[VenueOut]
