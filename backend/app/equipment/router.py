import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.equipment.models import EquipmentLineStatus
from app.equipment.schemas import (
    EquipmentAvailabilityOut,
    EquipmentEventsOut,
    EquipmentLineOut,
    EquipmentLinesOut,
    EquipmentLineWrite,
    EquipmentReviewWrite,
    EquipmentTypesOut,
    ReservationWrite,
    TechStaffOut,
    TechStaffWrite,
)
from app.equipment.service import equipment_service
from app.equipment.tech_staff_service import tech_staff_service
from app.notification.service import Notifier, get_notifier
from app.user.dependencies import get_current_user, require_user_roles
from app.user.models import User, UserRole

types_router = APIRouter(prefix="/api/v1/equipment-types", tags=["equipment"])
router = APIRouter(prefix="/api/v1/equipment-lines", tags=["equipment"])
# An event's lines hang off the event, like its venue bookings do.
events_router = APIRouter(prefix="/api/v1/events", tags=["equipment"])
# The caller's own events, like /me/registrations and /me/event-requests (SCRUM-110).
me_router = APIRouter(prefix="/api/v1/me", tags=["equipment"])

SignedIn = Annotated[User, Depends(get_current_user)]
Coordinator = Annotated[User, Depends(require_user_roles(UserRole.COORDINATOR))]
TechSupport = Annotated[User, Depends(require_user_roles(UserRole.TECH_SUPPORT))]


@types_router.get("", response_model=EquipmentTypesOut)
def equipment_types(_: SignedIn, db: Session = Depends(get_db)) -> EquipmentTypesOut:
    return EquipmentTypesOut(equipment_types=equipment_service.types(db))


@me_router.get("/equipment-events", response_model=EquipmentEventsOut)
def my_equipment_events(
    coordinator: Coordinator, db: Session = Depends(get_db), now: datetime = Depends(get_now)
) -> EquipmentEventsOut:
    return EquipmentEventsOut(events=equipment_service.my_events(db, coordinator, now))


@events_router.get("/{event_id}/equipment-lines", response_model=EquipmentLinesOut)
def event_lines(event_id: uuid.UUID, coordinator: Coordinator, db: Session = Depends(get_db)) -> EquipmentLinesOut:
    return EquipmentLinesOut(lines=equipment_service.for_event(db, coordinator, event_id))


@events_router.post("/{event_id}/equipment-lines", status_code=201, response_model=EquipmentLineOut)
def add_line(
    event_id: uuid.UUID, body: EquipmentLineWrite, coordinator: Coordinator, db: Session = Depends(get_db)
) -> EquipmentLineOut:
    return equipment_service.create(db, coordinator, event_id, body)


@events_router.get("/{event_id}/tech-staff", response_model=TechStaffOut)
def event_tech_staff(event_id: uuid.UUID, coordinator: Coordinator, db: Session = Depends(get_db)) -> TechStaffOut:
    """US14 (SCRUM-134): whether staff can be assigned, who is, who's available, and the log (AC 1, 2, 6)."""
    return tech_staff_service.for_event(db, coordinator, event_id)


@events_router.post("/{event_id}/tech-staff", status_code=201, response_model=TechStaffOut)
def assign_tech_staff(
    event_id: uuid.UUID,
    body: TechStaffWrite,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
    notifier: Notifier = Depends(get_notifier),
) -> TechStaffOut:
    """US14 AC 3, 4: assign one or more Tech support staff, all or none, and notify each."""
    return tech_staff_service.assign(db, coordinator, event_id, body.staff_user_ids, now, notifier)


@events_router.delete("/{event_id}/tech-staff/{staff_user_id}", status_code=204, response_class=Response)
def unassign_tech_staff(
    event_id: uuid.UUID,
    staff_user_id: uuid.UUID,
    coordinator: Coordinator,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> None:
    """US14 AC 5: unassign before the event starts; reassigning is this, then an assign."""
    tech_staff_service.unassign(db, coordinator, event_id, staff_user_id, now)


@router.get("", response_model=EquipmentLinesOut)
def pending_lines(
    _: TechSupport, db: Session = Depends(get_db), status: Literal["pending", "approved"] = "pending"
) -> EquipmentLinesOut:
    # Pending lines to review (US26 AC 3), or approved lines to reserve (US27, SCRUM-131).
    return EquipmentLinesOut(lines=equipment_service.queue(db, EquipmentLineStatus(status)))


@router.post("/{line_id}/availability-check", response_model=EquipmentAvailabilityOut)
def check_line_availability(
    line_id: uuid.UUID, checker: TechSupport, db: Session = Depends(get_db), now: datetime = Depends(get_now)
) -> EquipmentAvailabilityOut:
    """US5 (SCRUM-125): is the line's type and quantity available for its event's times? The outcome is
    recorded on the line (D64); nothing is reserved."""
    return equipment_service.check_availability(db, checker, line_id, now)


@router.post("/{line_id}/reservation", status_code=201, response_model=EquipmentLineOut)
def reserve_line(
    line_id: uuid.UUID, reserver: TechSupport, db: Session = Depends(get_db), body: ReservationWrite | None = None
) -> EquipmentLineOut:
    """US27 (SCRUM-131): reserve the approved line's full quantity (AC 1, 6); no fields to send."""
    return equipment_service.reserve(db, reserver, line_id)


@router.delete("/{line_id}/reservation", status_code=204, response_class=Response)
def release_line(line_id: uuid.UUID, _: TechSupport, db: Session = Depends(get_db)) -> None:
    """US27 AC 5: release the line's reservation (D74: it's deleted)."""
    equipment_service.release(db, line_id)


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
