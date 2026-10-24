import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.equipment.schemas import (
    EquipmentLineOut,
    EquipmentLinesOut,
    EquipmentLineWrite,
    EquipmentReviewWrite,
    EquipmentTypesOut,
)
from app.equipment.service import equipment_service
from app.notification.service import Notifier, get_notifier
from app.user.dependencies import get_current_user, require_user_roles
from app.user.models import User, UserRole

types_router = APIRouter(prefix="/api/v1/equipment-types", tags=["equipment"])
router = APIRouter(prefix="/api/v1/equipment-lines", tags=["equipment"])
# An event's lines hang off the event, like its venue bookings do.
events_router = APIRouter(prefix="/api/v1/events", tags=["equipment"])

SignedIn = Annotated[User, Depends(get_current_user)]
Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]
TechSupport = Annotated[User, Depends(require_user_roles(UserRole.TECH_SUPPORT))]


@types_router.get("", response_model=EquipmentTypesOut)
def equipment_types(_: SignedIn, db: Session = Depends(get_db)) -> EquipmentTypesOut:
    return EquipmentTypesOut(equipment_types=equipment_service.types(db))


@events_router.get("/{event_id}/equipment-lines", response_model=EquipmentLinesOut)
def event_lines(event_id: uuid.UUID, coordinator: Coordinator, db: Session = Depends(get_db)) -> EquipmentLinesOut:
    return EquipmentLinesOut(lines=equipment_service.for_event(db, coordinator, event_id))


@events_router.post("/{event_id}/equipment-lines", status_code=201, response_model=EquipmentLineOut)
def add_line(
    event_id: uuid.UUID, body: EquipmentLineWrite, coordinator: Coordinator, db: Session = Depends(get_db)
) -> EquipmentLineOut:
    return equipment_service.create(db, coordinator, event_id, body)


@router.get("", response_model=EquipmentLinesOut)
def pending_lines(
    _: TechSupport, db: Session = Depends(get_db), status: Literal["pending"] = "pending"
) -> EquipmentLinesOut:
    # Only the pending queue for now (AC 3); `status` is in the URL so other filters can follow.
    return EquipmentLinesOut(lines=equipment_service.pending(db))


@router.patch("/{line_id}", response_model=EquipmentLineOut)
def edit_line(
    line_id: uuid.UUID, body: EquipmentLineWrite, coordinator: Coordinator, db: Session = Depends(get_db)
) -> EquipmentLineOut:
    return equipment_service.edit(db, coordinator, line_id, body)


@router.delete("/{line_id}", status_code=204, response_class=Response)
def remove_line(line_id: uuid.UUID, coordinator: Coordinator, db: Session = Depends(get_db)) -> None:
    equipment_service.remove(db, coordinator, line_id)


@router.post("/{line_id}/review", response_model=EquipmentLineOut)
def review_line(
    line_id: uuid.UUID,
    body: EquipmentReviewWrite,
    reviewer: TechSupport,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> EquipmentLineOut:
    return equipment_service.review(db, reviewer, line_id, body, now, notifier)
