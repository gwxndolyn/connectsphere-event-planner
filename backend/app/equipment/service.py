import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentReservation, EquipmentType
from app.equipment.schemas import (
    AvailabilityCheckOut,
    AvailabilityTypeOut,
    AvailabilityWindowOut,
    EquipmentAvailabilityOut,
    EquipmentEventOut,
    EquipmentLineOut,
    EquipmentLineWrite,
    EquipmentReviewWrite,
    EquipmentTypeOut,
    LineEventOut,
)
from app.event.models import Event, EventStatus
from app.event.self_decision import refuse_self_decision
from app.notification.service import Notifier
from app.user.models import User, UserRole

logger = logging.getLogger(__name__)

# SCRUM-109 (TC-US26-10): only an event being planned or already confirmed takes equipment lines.
ELIGIBLE_STATUSES = (EventStatus.PLANNING, EventStatus.CONFIRMED)
# The body's checked fields, in order, so a form marks them top to bottom.
LINE_FIELDS = ("equipment_type_id", "quantity")
# DECISION-PENDING: D41 — one pending or approved line per type per event (SCRUM-108's partial unique index).
ONE_LIVE_PER_TYPE = "equipment_request_lines_one_live_per_type"


def may_manage(event: Event, coordinator: User) -> bool:
    """Whether this coordinator may add, list, edit and remove the event's lines: only the coordinator
    assigned to it (AC 1: "an event they manage"), whoever added the line. An unassigned event has
    nobody who may."""
    # DECISION-PENDING: D20 — as for venue bookings: events.coordinator_id, since US10a (SCRUM-13).
    return coordinator.holds(UserRole.COORDINATOR) and event.coordinator_id == coordinator.id


def _type_id(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def _clean(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    """Checks the fields present in `values` (AC 4), collecting every invalid one. Returns them with
    notes trimmed and blank notes as null."""
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {}
    if "equipment_type_id" in values:
        type_id = _type_id(values["equipment_type_id"])
        equipment_type = db.get(EquipmentType, type_id) if type_id else None
        if equipment_type is None:
            errors["equipment_type_id"] = "Choose an equipment type from the catalogue."
        else:
            cleaned["equipment_type_id"] = equipment_type.id
    if "quantity" in values:
        quantity = values["quantity"]
        # bool is an int in Python; JSON true is not a quantity.
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            errors["quantity"] = "Quantity must be a whole number of at least 1."
        else:
            cleaned["quantity"] = quantity
    if "notes" in values:
        cleaned["notes"] = (values["notes"] or "").strip() or None
    if errors:
        ordered = {field: errors[field] for field in LINE_FIELDS if field in errors}
        raise DomainError(422, "INVALID_EQUIPMENT_LINE", fields=list(ordered), errors=ordered)
    return cleaned


def _duplicate() -> DomainError:
    return DomainError(
        409,
        "DUPLICATE_EQUIPMENT_TYPE",
        fields=["equipment_type_id"],
        message="This event already has a pending or approved line for that equipment type. Change its quantity instead.",
    )


def _check_not_duplicate(
    db: Session, event_id: uuid.UUID, type_id: uuid.UUID, line_id: uuid.UUID | None = None
) -> None:
    """D41, asked first so the refusal is a 409 rather than the index's IntegrityError. A rejected
    line doesn't count, and a line is never a duplicate of itself."""
    query = select(EquipmentRequestLine.id).where(
        EquipmentRequestLine.event_id == event_id,
        EquipmentRequestLine.equipment_type_id == type_id,
        EquipmentRequestLine.status != EquipmentLineStatus.REJECTED,
    )
    if line_id is not None:
        query = query.where(EquipmentRequestLine.id != line_id)
    if db.scalars(query.limit(1)).first() is not None:
        raise _duplicate()


def _not_pending(line: EquipmentRequestLine) -> DomainError:
    return DomainError(409, "LINE_NOT_PENDING", status=line.status.value)


def _out(line: EquipmentRequestLine, event: Event, equipment_type: EquipmentType) -> EquipmentLineOut:
    return EquipmentLineOut(
        id=line.id,
        event=LineEventOut.model_validate(event),
        equipment_type=EquipmentTypeOut.model_validate(equipment_type),
        quantity=line.quantity,
        notes=line.notes,
        status=line.status,
        review_note=line.review_note,
        requested_by_user_id=line.requested_by_user_id,
        reviewed_by_user_id=line.reviewed_by_user_id,
        reviewed_at=line.reviewed_at,
        availability_check=_check_out(line),
        created_at=line.created_at,
        updated_at=line.updated_at,
    )


def _check_out(line: EquipmentRequestLine) -> AvailabilityCheckOut | None:
    if line.availability_checked_at is None:
        return None
    return AvailabilityCheckOut(
        sufficient=line.availability_sufficient,
        shortfall=line.availability_shortfall,
        checked_by_user_id=line.availability_checked_by_user_id,
        checked_at=line.availability_checked_at,
    )


def _clear_check(line: EquipmentRequestLine) -> None:
    line.availability_checked_at = None
    line.availability_checked_by_user_id = None
    line.availability_sufficient = None
    line.availability_shortfall = None


def _lines(db: Session, *conditions: Any) -> list[EquipmentLineOut]:
    rows = db.execute(
        select(EquipmentRequestLine, Event, EquipmentType)
        .join(Event, Event.id == EquipmentRequestLine.event_id)
        .join(EquipmentType, EquipmentType.id == EquipmentRequestLine.equipment_type_id)
        .where(*conditions)
        .order_by(EquipmentRequestLine.created_at, EquipmentRequestLine.id)
    )
    return [_out(line, event, equipment_type) for line, event, equipment_type in rows]


class EquipmentService:
    """US26 (SCRUM-94): a coordinator's equipment lines and Tech Support's review of them."""

    def types(self, db: Session) -> list[EquipmentTypeOut]:
        """The catalogue (AC 4), by name."""
        return [
            EquipmentTypeOut.model_validate(equipment_type)
            for equipment_type in db.scalars(select(EquipmentType).order_by(EquipmentType.name))
        ]

    def my_events(self, db: Session, coordinator: User, now: datetime) -> list[EquipmentEventOut]:
        """The events this coordinator can add lines to (SCRUM-110, TC-US26-20): the ones assigned to
        them (D20) in an eligible status. The event-request routes hide these (D11). Events not over
        yet come first, soonest first, then ended ones, most recent first (PR #78 review): ended ones
        stay listed because the API still takes lines for them (the rule is status only)."""
        events = db.scalars(
            select(Event).where(Event.coordinator_id == coordinator.id, Event.status.in_(ELIGIBLE_STATUSES))
        ).all()
        # Planning and confirmed events always have both times (events_final_fields_required).
        upcoming = sorted((e for e in events if e.end_at >= now), key=lambda e: (e.start_at, e.name, str(e.id)))
        ended = sorted((e for e in events if e.end_at < now), key=lambda e: (e.start_at, e.name, str(e.id)), reverse=True)
        return [EquipmentEventOut.model_validate(event) for event in upcoming + ended]

    def for_event(self, db: Session, coordinator: User, event_id: uuid.UUID) -> list[EquipmentLineOut]:
        """An event's lines in every status, oldest first, for its assigned coordinator."""
        self._managed_event(db, coordinator, event_id)
        return _lines(db, EquipmentRequestLine.event_id == event_id)

    def create(
        self, db: Session, coordinator: User, event_id: uuid.UUID, body: EquipmentLineWrite
    ) -> EquipmentLineOut:
        """AC 1: a pending line for one equipment type, recording who asked."""
        # FOR SHARE: a concurrent status change waits for this request.
        event = self._managed_event(db, coordinator, event_id, lock=True)
        if event.status not in ELIGIBLE_STATUSES:
            raise DomainError(409, "EVENT_NOT_ELIGIBLE", status=event.status.value)
        cleaned = _clean(db, body.model_dump())
        _check_not_duplicate(db, event.id, cleaned["equipment_type_id"])

        line = EquipmentRequestLine(event_id=event.id, requested_by_user_id=coordinator.id, **cleaned)
        db.add(line)
        self._commit(db)
        db.refresh(line)
        return _out(line, event, db.get(EquipmentType, line.equipment_type_id))

    def edit(
        self, db: Session, coordinator: User, line_id: uuid.UUID, body: EquipmentLineWrite
    ) -> EquipmentLineOut:
        """AC 2: a pending line's type, quantity or notes; only the fields sent change."""
        line, event = self._managed_line(db, coordinator, line_id)
        if line.status != EquipmentLineStatus.PENDING:
            raise _not_pending(line)
        cleaned = _clean(db, body.model_dump(exclude_unset=True))
        if "equipment_type_id" in cleaned:
            _check_not_duplicate(db, event.id, cleaned["equipment_type_id"], line.id)

        # US5 (D64): a recorded check is for one type and quantity; it no longer applies once either changes.
        if any(getattr(line, field) != cleaned[field] for field in LINE_FIELDS if field in cleaned):
            _clear_check(line)
        for field, value in cleaned.items():
            setattr(line, field, value)
        self._commit(db)
        db.refresh(line)
        return _out(line, event, db.get(EquipmentType, line.equipment_type_id))

    def remove(self, db: Session, coordinator: User, line_id: uuid.UUID) -> None:
        """AC 2: a pending line is deleted; a reviewed one stays as the record of the decision."""
        line, _ = self._managed_line(db, coordinator, line_id)
        if line.status != EquipmentLineStatus.PENDING:
            raise _not_pending(line)
        db.delete(line)
        db.commit()

    def pending(self, db: Session) -> list[EquipmentLineOut]:
        """Tech Support's queue (AC 3): pending lines from every event, oldest first."""
        return _lines(db, EquipmentRequestLine.status == EquipmentLineStatus.PENDING)

    def check_availability(
        self, db: Session, checker: User, line_id: uuid.UUID, now: datetime
    ) -> EquipmentAvailabilityOut:
        """US5 (SCRUM-125): the line's type and quantity against its stock, less units out of service
        (AC 3) and units reserved for other events overlapping this one's own times (AC 2, 6). The outcome
        is recorded on the line, replacing the last (AC 5, D64); it never reserves or reviews. FOR UPDATE,
        so a coordinator's edit, which clears the check, waits for it."""
        line = db.scalars(
            select(EquipmentRequestLine).where(EquipmentRequestLine.id == line_id).with_for_update()
        ).one_or_none()
        if line is None:
            raise DomainError(404, "NOT_FOUND")
        event = db.get(Event, line.event_id)
        equipment_type = db.get(EquipmentType, line.equipment_type_id)

        # Overlap on the events' own [start, end): back-to-back doesn't overlap, as for venues (D21). No
        # venue setup or turnaround (AC 6), and the line's own event isn't counted against itself (AC 2).
        reserved_elsewhere = db.scalar(
            select(func.coalesce(func.sum(EquipmentReservation.quantity), 0))
            .join(Event, Event.id == EquipmentReservation.event_id)
            .where(
                EquipmentReservation.equipment_type_id == equipment_type.id,
                EquipmentReservation.event_id != event.id,
                Event.start_at < event.end_at,
                Event.end_at > event.start_at,
            )
        )
        # Stock can fall below what's reserved (units going out of service later), so never below 0.
        available = max(
            equipment_type.total_quantity - equipment_type.out_of_service_quantity - reserved_elsewhere, 0
        )
        line.availability_sufficient = available >= line.quantity
        line.availability_shortfall = max(line.quantity - available, 0)
        line.availability_checked_by_user_id = checker.id
        line.availability_checked_at = now
        db.commit()
        return EquipmentAvailabilityOut(
            line_id=line.id,
            equipment_type=AvailabilityTypeOut.model_validate(equipment_type),
            window=AvailabilityWindowOut(starts_at=event.start_at, ends_at=event.end_at),
            requested=line.quantity,
            total=equipment_type.total_quantity,
            out_of_service=equipment_type.out_of_service_quantity,
            reserved_elsewhere=reserved_elsewhere,
            available=available,
            sufficient=line.availability_sufficient,
            shortfall=line.availability_shortfall,
            checked_by_user_id=checker.id,
            checked_at=now,
        )

    def review(
        self,
        db: Session,
        reviewer: User,
        line_id: uuid.UUID,
        body: EquipmentReviewWrite,
        now: datetime,
        notifier: Notifier,
    ) -> EquipmentLineOut:
        """AC 3, 6: approve the line for its full quantity, or reject it, with an optional note
        (D43). FOR UPDATE, so a second review or a coordinator's edit waits and then sees it."""
        line = db.scalars(
            select(EquipmentRequestLine).where(EquipmentRequestLine.id == line_id).with_for_update()
        ).one_or_none()
        if line is None:
            raise DomainError(404, "NOT_FOUND")
        # D51: not a line they requested, nor one for an event they now coordinate. The first half is
        # also a CHECK (equipment_request_lines_reviewer_not_requester).
        refuse_self_decision(reviewer, created_by_user_id=line.requested_by_user_id, event=db.get(Event, line.event_id))
        if line.status != EquipmentLineStatus.PENDING:
            raise _not_pending(line)

        line.status = EquipmentLineStatus(body.decision)
        # DECISION-PENDING: D43 — the note is optional for both decisions (AC 3 doesn't require one).
        line.review_note = (body.note or "").strip() or None
        line.reviewed_by_user_id = reviewer.id
        line.reviewed_at = now
        db.commit()
        db.refresh(line)

        event = db.get(Event, line.event_id)
        equipment_type = db.get(EquipmentType, line.equipment_type_id)
        result = _out(line, event, equipment_type)
        self._notify_coordinator(db, notifier, line, event, equipment_type)
        return result

    def _managed_event(self, db: Session, coordinator: User, event_id: uuid.UUID, lock: bool = False) -> Event:
        """The event, if this coordinator manages it. Anyone else gets 404, as for venue bookings (D20),
        and so does a draft, which is owner-only (D11)."""
        query = select(Event).where(Event.id == event_id)
        event = db.scalars(query.with_for_update(read=True) if lock else query).one_or_none()
        if event is None or event.status == EventStatus.DRAFT or not may_manage(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        return event

    def _managed_line(
        self, db: Session, coordinator: User, line_id: uuid.UUID
    ) -> tuple[EquipmentRequestLine, Event]:
        """The line, locked, if this coordinator manages its event; 404 otherwise."""
        line = db.scalars(
            select(EquipmentRequestLine).where(EquipmentRequestLine.id == line_id).with_for_update()
        ).one_or_none()
        event = db.get(Event, line.event_id) if line is not None else None
        if line is None or event is None or not may_manage(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        return line, event

    def _commit(self, db: Session) -> None:
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint == ONE_LIVE_PER_TYPE:
                # Another request for the same type committed between the check and this commit.
                raise _duplicate() from None
            raise

    def _notify_coordinator(
        self,
        db: Session,
        notifier: Notifier,
        line: EquipmentRequestLine,
        event: Event,
        equipment_type: EquipmentType,
    ) -> None:
        """AC 5: the coordinator who asked for the line hears the decision. Runs after the commit;
        a failure is logged and the review stands."""
        try:
            requester = db.get(User, line.requested_by_user_id)
            notifier.equipment_line_reviewed(
                email=requester.email,
                line_id=line.id,
                event_name=event.name or event.request_reference or str(event.id),
                equipment_type=equipment_type.name,
                quantity=line.quantity,
                decision=line.status.value,
                note=line.review_note,
            )
        except Exception:
            logger.exception("could not notify the coordinator about equipment line %s", line.id)


equipment_service = EquipmentService()
