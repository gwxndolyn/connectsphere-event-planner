"""US14 (SCRUM-17, SCRUM-134): the event's coordinator assigns Tech support staff to it, and unassigns them.

Each row of tech_staff_assignments is one assignment, active until it's unassigned; the rows are also the
log (D79). Reassigning is an unassign and an assign.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentType, TechStaffAssignment
from app.equipment.schemas import PersonOut, TechStaffAssignedOut, TechStaffLogEntryOut, TechStaffOut
from app.equipment.service import ELIGIBLE_STATUSES, managed_event
from app.event.models import Event
from app.notification.service import Notifier
from app.user.models import User, UserRole
from app.venue.primary import attendee_venue, primary_venues

logger = logging.getLogger(__name__)


def _eligible(db: Session, event: Event) -> bool:
    """AC 1. D80 (decided by the acting PO, 31 Oct): an approved technical support request is an approved
    equipment line (US26), on an event in planning or confirmed."""
    if event.status not in ELIGIBLE_STATUSES:
        return False
    approved = select(EquipmentRequestLine.id).where(
        EquipmentRequestLine.event_id == event.id, EquipmentRequestLine.status == EquipmentLineStatus.APPROVED
    )
    return db.scalars(approved.limit(1)).first() is not None


def _started(event: Event, now: datetime) -> bool:
    # AC 5: changes only before the event starts.
    return event.start_at is not None and now >= event.start_at


def _busy(db: Session, event: Event, staff_user_ids: list[uuid.UUID] | None = None) -> set[uuid.UUID]:
    """Staff actively assigned to another event overlapping this one (AC 2). D81 (decided by the acting PO,
    31 Oct): the events' own times, [start, end), with no venue setup or turnaround, so back-to-back
    doesn't overlap."""
    query = (
        select(TechStaffAssignment.staff_user_id)
        .join(Event, Event.id == TechStaffAssignment.event_id)
        .where(
            TechStaffAssignment.unassigned_at.is_(None),
            TechStaffAssignment.event_id != event.id,
            Event.start_at < event.end_at,
            Event.end_at > event.start_at,
        )
    )
    if staff_user_ids is not None:
        query = query.where(TechStaffAssignment.staff_user_id.in_(staff_user_ids))
    return set(db.scalars(query))


def _lock_staff(db: Session, staff_user_ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
    """The staff members' rows FOR UPDATE, in id order so two requests can't deadlock: two assignments of
    one person take turns, and the second sees the first's (AC 2, TC-US14-13)."""
    query = select(User).where(User.id.in_(staff_user_ids)).order_by(User.id).with_for_update()
    return {user.id: user for user in db.scalars(query)}


def _active(db: Session, event_id: uuid.UUID, staff_user_ids: list[uuid.UUID]) -> list[TechStaffAssignment]:
    return list(
        db.scalars(
            select(TechStaffAssignment).where(
                TechStaffAssignment.event_id == event_id,
                TechStaffAssignment.staff_user_id.in_(staff_user_ids),
                TechStaffAssignment.unassigned_at.is_(None),
            )
        )
    )


def _named(staff_user_ids: list[uuid.UUID]) -> list[str]:
    return [str(staff_user_id) for staff_user_id in staff_user_ids]


def _person(user: User) -> PersonOut:
    return PersonOut(id=user.id, name=user.display_name)


class TechStaffService:
    def for_event(self, db: Session, coordinator: User, event_id: uuid.UUID) -> TechStaffOut:
        """Who's assigned, who's available, and the log (AC 1, 2, 6), for the event's coordinator (D20)."""
        return self._out(db, managed_event(db, coordinator, event_id))

    def assign(
        self,
        db: Session,
        coordinator: User,
        event_id: uuid.UUID,
        staff_user_ids: list[uuid.UUID],
        now: datetime,
        notifier: Notifier,
    ) -> TechStaffOut:
        """AC 3: every one of them, or nobody. Each is notified after the commit (AC 4)."""
        event = managed_event(db, coordinator, event_id, lock=True)
        if not _eligible(db, event):
            raise DomainError(409, "NO_APPROVED_TECH_REQUEST")
        if _started(event, now):
            raise DomainError(409, "EVENT_STARTED")
        wanted = list(dict.fromkeys(staff_user_ids))

        staff = _lock_staff(db, wanted)
        invalid = [
            staff_user_id
            for staff_user_id in wanted
            if staff_user_id not in staff
            or not staff[staff_user_id].is_active
            or not staff[staff_user_id].holds(UserRole.TECH_SUPPORT)
        ]
        if invalid:
            raise DomainError(422, "INVALID_STAFF", staff_user_ids=_named(invalid))
        already = {row.staff_user_id for row in _active(db, event.id, wanted)}
        if already:
            raise DomainError(409, "ALREADY_ASSIGNED", staff_user_ids=_named([s for s in wanted if s in already]))
        busy = _busy(db, event, wanted)
        if busy:
            raise DomainError(409, "STAFF_UNAVAILABLE", staff_user_ids=_named([s for s in wanted if s in busy]))

        for staff_user_id in wanted:
            db.add(
                TechStaffAssignment(
                    event_id=event.id, staff_user_id=staff_user_id, assigned_by_user_id=coordinator.id, assigned_at=now
                )
            )
        db.commit()
        self._notify(db, notifier, event, [staff[staff_user_id] for staff_user_id in wanted])
        return self._out(db, event)

    def unassign(
        self, db: Session, coordinator: User, event_id: uuid.UUID, staff_user_id: uuid.UUID, now: datetime
    ) -> None:
        """AC 5, 6: stamps who unassigned them and when; the row stays as the log."""
        event = managed_event(db, coordinator, event_id, lock=True)
        if _started(event, now):
            raise DomainError(409, "EVENT_STARTED")
        row = db.scalars(
            select(TechStaffAssignment)
            .where(
                TechStaffAssignment.event_id == event.id,
                TechStaffAssignment.staff_user_id == staff_user_id,
                TechStaffAssignment.unassigned_at.is_(None),
            )
            .with_for_update()
        ).one_or_none()
        if row is None:
            raise DomainError(409, "NOT_ASSIGNED")
        row.unassigned_by_user_id, row.unassigned_at = coordinator.id, now
        db.commit()

    def _out(self, db: Session, event: Event) -> TechStaffOut:
        rows = db.scalars(select(TechStaffAssignment).where(TechStaffAssignment.event_id == event.id)).all()
        user_ids = {row.staff_user_id for row in rows} | {row.assigned_by_user_id for row in rows}
        user_ids |= {row.unassigned_by_user_id for row in rows if row.unassigned_by_user_id is not None}
        people = {user.id: _person(user) for user in db.scalars(select(User).where(User.id.in_(user_ids)))}

        active = sorted((row for row in rows if row.unassigned_at is None), key=lambda row: row.assigned_at)
        log: list[TechStaffLogEntryOut] = []
        for row in rows:
            staff = people[row.staff_user_id]
            log.append(TechStaffLogEntryOut(action="assigned", staff=staff, by=people[row.assigned_by_user_id], at=row.assigned_at))
            if row.unassigned_at is not None:
                log.append(
                    TechStaffLogEntryOut(
                        action="unassigned", staff=staff, by=people[row.unassigned_by_user_id], at=row.unassigned_at
                    )
                )
        # Newest first; at the same moment, an unassign after the assign it ends.
        log.sort(key=lambda entry: (entry.at, entry.action == "unassigned"), reverse=True)

        eligible = _eligible(db, event)
        available: list[PersonOut] = []
        if eligible:
            unavailable = _busy(db, event) | {row.staff_user_id for row in active}
            candidates = db.scalars(
                select(User).where(User.roles.any(UserRole.TECH_SUPPORT), User.is_active.is_(True))
            )
            available = sorted(
                (_person(user) for user in candidates if user.id not in unavailable),
                key=lambda person: (person.name.lower(), str(person.id)),
            )
        return TechStaffOut(
            eligible=eligible,
            assigned=[
                TechStaffAssignedOut(
                    staff=people[row.staff_user_id], assigned_by=people[row.assigned_by_user_id], assigned_at=row.assigned_at
                )
                for row in active
            ],
            available=available,
            log=log,
        )

    def _notify(self, db: Session, notifier: Notifier, event: Event, staff: list[User]) -> None:
        """AC 4, after the commit; a failure is logged and the assignment stands. D82 (decided by the acting
        PO, 31 Oct): the venue attendees see (D70), and the technical requirements are the approved lines
        plus equipment_needs."""
        try:
            venue_name, location = attendee_venue(event, primary_venues(db, [event.id]).get(event.id))
            lines = db.execute(
                select(EquipmentRequestLine.quantity, EquipmentType.name)
                .join(EquipmentType, EquipmentType.id == EquipmentRequestLine.equipment_type_id)
                .where(
                    EquipmentRequestLine.event_id == event.id,
                    EquipmentRequestLine.status == EquipmentLineStatus.APPROVED,
                )
            ).all()
            equipment = sorted(f"{quantity} x {name}" for quantity, name in lines)
        except Exception:
            logger.exception("could not gather event %s's details for its Tech support staff", event.id)
            return
        for person in staff:
            try:
                notifier.tech_staff_assigned(
                    email=person.email,
                    event_id=event.id,
                    event_name=event.name,
                    starts_at=event.start_at,
                    ends_at=event.end_at,
                    venue_name=venue_name,
                    location=location,
                    equipment=equipment,
                    equipment_needs=event.equipment_needs,
                )
            except Exception:
                logger.exception("could not notify %s about event %s", person.id, event.id)


tech_staff_service = TechStaffService()
