import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.equipment.models import EquipmentLineStatus
from app.event.models import EventStatus


class EquipmentLineWrite(BaseModel):
    """Add and edit body (US26 AC 1, 2). The type and quantity arrive unchecked so the service can
    name every invalid field at once (`INVALID_EQUIPMENT_LINE`, TC-US26-07) instead of FastAPI's
    generic 422. Unknown fields such as `status` are rejected, so a coordinator can't review their own
    line. On edit, only the fields sent change."""

    model_config = ConfigDict(extra="forbid")

    equipment_type_id: Any = None
    quantity: Any = None
    notes: str | None = None


class EquipmentReviewWrite(BaseModel):
    """Tech Support's decision (AC 3). No quantity: approval is always the full requested quantity
    (AC 6), so sending one is rejected (TC-US26-13)."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str | None = None


class EquipmentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class EquipmentTypesOut(BaseModel):
    equipment_types: list[EquipmentTypeOut]


class LineEventOut(BaseModel):
    """Which event a line is for, so Tech Support's queue can say (TC-US26-11)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    start_at: datetime | None


class EquipmentEventOut(BaseModel):
    """An event the coordinator can add lines to, for the screen's picker (SCRUM-110)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str | None
    start_at: datetime | None
    status: EventStatus


class EquipmentEventsOut(BaseModel):
    events: list[EquipmentEventOut]


class AvailabilityCheckOut(BaseModel):
    """The line's latest US5 availability check (AC 5 "records the outcome", D64)."""

    sufficient: bool
    shortfall: int
    checked_by_user_id: uuid.UUID
    checked_at: datetime


class ReservationOut(BaseModel):
    """A line's reservation (US27, SCRUM-131, AC 4): its full quantity, who reserved it and when."""

    quantity: int
    reserved_by_user_id: uuid.UUID
    reserved_at: datetime
    # D75: nothing cancels an event yet (US9), so a cancelled event's reservation counts as released.
    released_because_event_cancelled: bool


class ReservationWrite(BaseModel):
    """Reserving takes no fields: always the line's full approved quantity (US27 AC 6), so a quantity
    sent is a 422."""

    model_config = ConfigDict(extra="forbid")


class EquipmentLineOut(BaseModel):
    id: uuid.UUID
    event: LineEventOut
    equipment_type: EquipmentTypeOut
    quantity: int
    notes: str | None
    status: EquipmentLineStatus
    review_note: str | None
    requested_by_user_id: uuid.UUID
    reviewed_by_user_id: uuid.UUID | None
    reviewed_at: datetime | None
    # US5 (SCRUM-125): null until Tech Support checks it, and again after its quantity or type is edited.
    availability_check: AvailabilityCheckOut | None
    # US27 (SCRUM-131): the line's reservation, or null.
    reservation: ReservationOut | None
    created_at: datetime
    updated_at: datetime


class EquipmentLinesOut(BaseModel):
    lines: list[EquipmentLineOut]


class AvailabilityTypeOut(BaseModel):
    """The checked type, with where it's kept (US5 AC 7: for reference only)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    storage_location: str | None


class AvailabilityWindowOut(BaseModel):
    """The event's own times; no venue setup or turnaround (US5 AC 6)."""

    starts_at: datetime
    ends_at: datetime


class EquipmentAvailabilityOut(BaseModel):
    """POST /api/v1/equipment-lines/{id}/availability-check (US5, SCRUM-125): whether the line's type and
    quantity are available for its event's times (AC 1–4). The outcome is recorded on the line; nothing is
    reserved (AC 5, D64)."""

    line_id: uuid.UUID
    equipment_type: AvailabilityTypeOut
    window: AvailabilityWindowOut
    requested: int
    total: int
    out_of_service: int
    reserved_elsewhere: int
    available: int
    sufficient: bool
    shortfall: int
    checked_by_user_id: uuid.UUID
    checked_at: datetime


class TechStaffWrite(BaseModel):
    """Assign body (US14, SCRUM-134, AC 3): one or more Tech support users, all assigned or none."""

    model_config = ConfigDict(extra="forbid")

    staff_user_ids: list[uuid.UUID] = Field(min_length=1)


class PersonOut(BaseModel):
    """A staff member or the coordinator who acted: their full name, else their email."""

    id: uuid.UUID
    name: str


class TechStaffAssignedOut(BaseModel):
    staff: PersonOut
    assigned_by: PersonOut
    assigned_at: datetime


class TechStaffLogEntryOut(BaseModel):
    """One assign or unassign (AC 6): who it was, who did it and when."""

    action: Literal["assigned", "unassigned"]
    staff: PersonOut
    by: PersonOut
    at: datetime


class TechStaffOut(BaseModel):
    """GET, and POST's answer, for /api/v1/events/{id}/tech-staff (US14, SCRUM-134)."""

    # AC 1 (D80): an approved equipment line, and the event in planning or confirmed.
    eligible: bool
    assigned: list[TechStaffAssignedOut]
    # AC 2 (D81): active Tech support users not on an overlapping event, nor already assigned here;
    # empty while the event isn't eligible.
    available: list[PersonOut]
    # AC 6: newest first.
    log: list[TechStaffLogEntryOut]
