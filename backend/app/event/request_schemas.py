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


class CoordinatorOut(BaseModel):
    """The assigned coordinator as the organiser sees them (SCRUM-13 AC 8): `name` is the full name.

    A user with no full name yet (not every account has a profile) shows their email instead, so
    every real account should have one. The seeded users do.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str = Field(validation_alias="display_name")


class CoordinatorOptionOut(CoordinatorOut):
    """A picker row for the Lead, who can tell people apart by email."""

    email: str


class OrganiserOut(CoordinatorOptionOut):
    pass


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
    # null = unassigned; the screens show "Unassigned" (SCRUM-13 AC 8)
    coordinator: CoordinatorOut | None


class UnassignedRequestOut(EventRequestOut):
    """A queue row: everything the Lead needs before assigning (SCRUM-13 AC 2)."""

    organiser: OrganiserOut | None = Field(validation_alias="created_by")


class UnassignedRequestsOut(BaseModel):
    event_requests: list[UnassignedRequestOut]


class CoordinatorOptionsOut(BaseModel):
    coordinators: list[CoordinatorOptionOut]


class AssignmentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coordinator_id: uuid.UUID


class EventRequestsOut(BaseModel):
    event_requests: list[EventRequestOut]