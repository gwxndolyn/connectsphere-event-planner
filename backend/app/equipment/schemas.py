import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.equipment.models import EquipmentLineStatus


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
    created_at: datetime
    updated_at: datetime


class EquipmentLinesOut(BaseModel):
    lines: list[EquipmentLineOut]
