import uuid
from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.equipment.models import (
    EquipmentRequestLine,
    EquipmentReservation,
    EquipmentType,
)
from app.event.change_decision_schemas import (
    ClearFlagWrite,
    FlagTargetOut,
    ReviewFlagOut,
)
from app.event.models import Event, EventReviewFlag, ReviewFlagKind
from app.event.request_schemas import CoordinatorOut
from app.event.request_service import is_assigned_coordinator
from app.user.models import User
from app.venue.models import LIVE_BOOKING_STATUSES, Venue, VenueBooking

NOTE_MAX_LENGTH = 1000  # as a rejection reason


def resolved(db: Session, flag: EventReviewFlag) -> bool:
    """DECISION-PENDING: D104 — a flag whose booking was withdrawn or rejected, or whose reservation was released,
    reads as resolved. Derived on every read and never written: the clearance needs a person (the CHECK), and a
    withdrawal or release names none."""
    if flag.kind == ReviewFlagKind.VENUE_BOOKING:
        status = db.scalar(select(VenueBooking.status).where(VenueBooking.id == flag.venue_booking_id))
        return status not in LIVE_BOOKING_STATUSES
    if flag.kind == ReviewFlagKind.EQUIPMENT_RESERVATION:
        return not db.scalar(
            select(exists().where(EquipmentReservation.request_line_id == flag.equipment_request_line_id))
        )
    return False


def is_open(db: Session, flag: EventReviewFlag) -> bool:
    return flag.cleared_at is None and not resolved(db, flag)


def event_flags(db: Session, event_id: uuid.UUID) -> list[EventReviewFlag]:
    return db.scalars(
        select(EventReviewFlag).where(EventReviewFlag.event_id == event_id).order_by(EventReviewFlag.raised_at.desc(), EventReviewFlag.id)
    ).all()


def open_flags(db: Session, event_id: uuid.UUID) -> list[EventReviewFlag]:
    """What US18's readiness and US30a's queue and review wait on (D104, D106)."""
    return [flag for flag in event_flags(db, event_id) if is_open(db, flag)]


def flag_out(db: Session, flag: EventReviewFlag) -> ReviewFlagOut:
    target = None
    if flag.kind == ReviewFlagKind.VENUE_BOOKING:
        booking, venue = db.execute(
            select(VenueBooking, Venue).join(Venue, Venue.id == VenueBooking.venue_id).where(VenueBooking.id == flag.venue_booking_id)
        ).one()
        target = FlagTargetOut(id=booking.id, label=f"{booking.reference} · {venue.name}", status=booking.status.value)
    elif flag.kind == ReviewFlagKind.EQUIPMENT_RESERVATION:
        line, equipment_type = db.execute(
            select(EquipmentRequestLine, EquipmentType)
            .join(EquipmentType, EquipmentType.id == EquipmentRequestLine.equipment_type_id)
            .where(EquipmentRequestLine.id == flag.equipment_request_line_id)
        ).one()
        is_reserved = db.scalar(select(exists().where(EquipmentReservation.request_line_id == line.id)))
        target = FlagTargetOut(id=line.id, label=f"{equipment_type.name} × {line.quantity}", status="reserved" if is_reserved else "released")
    is_resolved = resolved(db, flag)
    cleared_by = db.get(User, flag.cleared_by_user_id) if flag.cleared_by_user_id else None
    return ReviewFlagOut(
        id=flag.id,
        event_id=flag.event_id,
        kind=flag.kind,
        target=target,
        fields=list(flag.fields),
        change_request_id=flag.change_request_id,
        raised_at=flag.raised_at,
        cleared_at=flag.cleared_at,
        cleared_by=CoordinatorOut.model_validate(cleared_by) if cleared_by else None,
        cleared_note=flag.cleared_note,
        resolved=is_resolved,
        open=flag.cleared_at is None and not is_resolved,
    )


class ReviewFlagService:
    """US29b AC 3 (SCRUM-142): the event's coordinator reviews what a significant change flagged, and clears each.
    DECISION-PENDING: D104 — the assigned coordinator, even when a Lead approved the change."""

    def list_for_event(self, db: Session, coordinator: User, event_id: uuid.UUID) -> list[ReviewFlagOut]:
        event = db.get(Event, event_id)
        if event is None or not is_assigned_coordinator(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        outs = [flag_out(db, flag) for flag in event_flags(db, event.id)]
        # Open first, then newest.
        return sorted(outs, key=lambda out: not out.open)

    def clear(self, db: Session, coordinator: User, flag_id: uuid.UUID, body: ClearFlagWrite, now: datetime) -> ReviewFlagOut:
        found = db.get(EventReviewFlag, flag_id)
        event = db.get(Event, found.event_id) if found else None
        if found is None or event is None or not is_assigned_coordinator(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        note = body.note.strip() if isinstance(body.note, str) else None
        if body.note is not None and not isinstance(body.note, str):
            raise DomainError(422, "INVALID_REVIEW_FLAG", fields=["note"], errors={"note": "The note must be text."})
        if note and len(note) > NOTE_MAX_LENGTH:
            raise DomainError(
                422, "INVALID_REVIEW_FLAG", fields=["note"], errors={"note": f"The note must be at most {NOTE_MAX_LENGTH} characters."}
            )
        # The event FOR SHARE, as a change decision locks it FOR UPDATE; the flag FOR UPDATE, so two clears queue.
        locked = db.scalars(
            select(Event).where(Event.id == event.id).with_for_update(read=True).execution_options(populate_existing=True)
        ).one()
        # Calvin's #125 review: the coordinator again, on the locked event, so a reassignment committed after the
        # first check refuses the old one.
        if not is_assigned_coordinator(locked, coordinator):
            raise DomainError(404, "NOT_FOUND")
        flag = db.scalars(
            select(EventReviewFlag).where(EventReviewFlag.id == flag_id).with_for_update().execution_options(populate_existing=True)
        ).one()
        if flag.cleared_at is not None:
            raise DomainError(409, "FLAG_ALREADY_CLEARED")
        flag.cleared_at = now
        flag.cleared_by_user_id = coordinator.id
        flag.cleared_note = note or None
        db.flush()
        result = flag_out(db, flag)
        db.commit()
        return result


review_flag_service = ReviewFlagService()
