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
    # SCRUM-84 AC 5: who approved or rejected it and when, and a rejection's reason. Null until decided,
    # and for events made before US17.
    decided_at: datetime | None = None
    decided_by: CoordinatorOut | None = None
    rejection_reason: str | None = None


class RequestRejectWrite(BaseModel):
    """Reject body (SCRUM-84 AC 3). Optional here so a missing reason is the API's own
    `MISSING_REQUIRED_FIELD`, like a blank one, not FastAPI's generic 422."""

    model_config = ConfigDict(extra="forbid")

    # Stored, logged and shown to the organiser, so kept to a readable length, as US4's notes are.
    reason: str | None = Field(default=None, max_length=1000)


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


class ReassignmentWrite(BaseModel):
    """SCRUM-83 AC 2: the different coordinator and why. A blank reason is refused by the service."""

    model_config = ConfigDict(extra="forbid")

    coordinator_id: uuid.UUID
    reason: str = Field(max_length=1000)


class TransferRequestWrite(BaseModel):
    """SCRUM-83 AC 6: a coordinator asks the Lead to move their event, with a reason."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=1000)


class AssignmentRecordOut(BaseModel):
    """One Assignment History entry (SCRUM-69 AC 3): whether it was an assignment or a reassignment,
    the Lead who did it, the coordinator and when."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: AssignmentKind
    assigned_by: PersonOut
    coordinator: PersonOut
    reason: str | None = None
    created_at: datetime


class AssignmentHistoryOut(BaseModel):
    assignments: list[AssignmentRecordOut]


class EventRequestsOut(BaseModel):
    event_requests: list[EventRequestOut]
