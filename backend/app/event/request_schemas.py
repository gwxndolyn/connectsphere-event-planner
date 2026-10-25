import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.event.models import AssignmentKind, EventStatus


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


class PersonOut(CoordinatorOut):
    """A person the Lead can tell apart by email."""

    email: str


class OrganiserOut(PersonOut):
    pass


class CoordinatorOptionOut(PersonOut):
    """A picker row (SCRUM-67): the coordinator and how many events they are currently planning."""

    planning_count: int


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


class AssignedRequestOut(EventRequestOut):
    """A row of the Lead's Assigned tab (SCRUM-86 AC 2): the request with its coordinator and status
    (already on `EventRequestOut`) and the event date: the start date once the event has one, else
    the first preferred date, null when neither is set."""

    event_date: date | None = None


class AssignedRequestsOut(BaseModel):
    event_requests: list[AssignedRequestOut]


class UnassignedRequestsOut(BaseModel):
    event_requests: list[UnassignedRequestOut]


class CoordinatorOptionsOut(BaseModel):
    coordinators: list[CoordinatorOptionOut]


class AssignmentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coordinator_id: uuid.UUID


class AssignmentRecordOut(BaseModel):
    """One Assignment History entry (SCRUM-69 AC 3): whether it was an assignment or a reassignment,
    the Lead who did it, the coordinator and when."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: AssignmentKind
    assigned_by: PersonOut
    coordinator: PersonOut
    created_at: datetime


class AssignmentHistoryOut(BaseModel):
    assignments: list[AssignmentRecordOut]


class EventRequestsOut(BaseModel):
    event_requests: list[EventRequestOut]
