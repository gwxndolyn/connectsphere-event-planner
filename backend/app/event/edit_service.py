import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.edit_schemas import (
    AuditEntryOut,
    ChangeRequestOut,
    CoordinatedEventOut,
    EventDetailsOut,
    EventEditOut,
    EventEditWrite,
    FieldChangeOut,
)
from app.event.models import (
    ChangeRequestStatus,
    DeliveryMode,
    Event,
    EventAuditEntry,
    EventChangeRequest,
    EventStatus,
)
from app.event.request_schemas import CoordinatorOut
from app.event.request_service import is_assigned_coordinator
from app.user.models import User

# Past the request stage: an event its coordinator can open (AC 1). The request stage is the request routes'.
COORDINATED_STATUSES = (EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.CANCELLED, EventStatus.COMPLETED)

# DECISION-PENDING: D83 — which fields are critical (the ticket doesn't list them): the schedule, the
# event's size and its format. Everything else is non-critical. The venue is booked through US22, not here.
CRITICAL_FIELDS = ("start_at", "end_at", "capacity", "expected_attendees", "delivery_mode")
NON_CRITICAL_FIELDS = (
    "name",
    "event_category",
    "purpose",
    "room_layout_preference",
    "accessibility_needs",
    "equipment_needs",
    "join_link",
)
# Body order, so a form marks errors top to bottom.
EDIT_FIELDS = (
    "name",
    "event_category",
    "purpose",
    "start_at",
    "end_at",
    "capacity",
    "expected_attendees",
    "delivery_mode",
    "room_layout_preference",
    "accessibility_needs",
    "equipment_needs",
    "join_link",
)
REQUIRED_FIELDS = {"name", "event_category", "purpose", "start_at", "end_at", "capacity", "expected_attendees", "delivery_mode"}
TEXT_FIELDS = set(NON_CRITICAL_FIELDS)
COUNT_FIELDS = ("capacity", "expected_attendees")
LABELS = {
    "name": "Event name",
    "event_category": "Category",
    "purpose": "Purpose",
    "start_at": "Start time",
    "end_at": "End time",
    "capacity": "Capacity",
    "expected_attendees": "Expected attendance",
    "delivery_mode": "Delivery mode",
    "room_layout_preference": "Room layout",
    "accessibility_needs": "Accessibility needs",
    "equipment_needs": "Equipment needs",
    "join_link": "Join link",
}
CATEGORY_MAX_LENGTH = 100  # D8, as on the request form

SAVED_MESSAGE = "Your changes are saved."
NOTHING_CHANGED_MESSAGE = "Nothing changed, so nothing was saved."


def _pending_message(fields: list[str]) -> str:
    labels = [LABELS[field].lower() for field in fields]
    named = labels[0] if len(labels) == 1 else f"{', '.join(labels[:-1])} and {labels[-1]}"
    return f"Your change to {named} is awaiting approval. The event keeps its current details until then."


def _json(value: Any) -> Any:
    """A value as the API writes it, for the audit log and change requests (JSON columns)."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    # D9: a time without its offset could be read in the wrong zone.
    return parsed if parsed.utcoffset() is not None else None


def _clean(values: dict[str, Any], event: Event) -> dict[str, Any]:
    """AC 4: checks every field sent, collecting each invalid one with a message that names it."""
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {}
    for field, value in values.items():
        label = LABELS[field]
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == "":
            if field in REQUIRED_FIELDS:
                errors[field] = f"{label} is required."
            else:
                cleaned[field] = None
            continue
        if field in TEXT_FIELDS:
            if not isinstance(value, str):
                errors[field] = f"{label} must be text."
            elif field == "event_category" and len(value) > CATEGORY_MAX_LENGTH:
                errors[field] = f"{label} must be at most {CATEGORY_MAX_LENGTH} characters."
            else:
                cleaned[field] = value
        elif field in COUNT_FIELDS:
            # bool is an int in Python; JSON true is not a count.
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                errors[field] = f"{label} must be a whole number of at least 1."
            else:
                cleaned[field] = value
        elif field == "delivery_mode":
            if value not in {mode.value for mode in DeliveryMode}:
                errors[field] = f"{label} must be in person or online."
            else:
                cleaned[field] = DeliveryMode(value)
        else:  # start_at, end_at
            instant = _instant(value)
            if instant is None:
                errors[field] = f"{label} must be a date and time with its timezone offset."
            else:
                cleaned[field] = instant

    starts = cleaned.get("start_at", event.start_at)
    ends = cleaned.get("end_at", event.end_at)
    if "start_at" not in errors and "end_at" not in errors and ends <= starts:
        # Name the field that was sent; if both were, the end is the one to move.
        field = "end_at" if "end_at" in values or "start_at" not in values else "start_at"
        errors[field] = "End time must be after the start time." if field == "end_at" else "Start time must be before the end time."
    if errors:
        ordered = {field: errors[field] for field in EDIT_FIELDS if field in errors}
        raise DomainError(422, "INVALID_EVENT_EDIT", fields=list(ordered), errors=ordered)
    return cleaned


def _change_request_out(request: EventChangeRequest) -> ChangeRequestOut:
    return ChangeRequestOut(
        id=request.id,
        status=request.status,
        changes=[FieldChangeOut(**change) for change in request.changes],
        requested_by=CoordinatorOut.model_validate(request.requested_by),
        created_at=request.created_at,
    )


class EventEditService:
    """US12 (SCRUM-15): the assigned coordinator edits an event in planning. Non-critical fields save at
    once (AC 2); a critical field sends the whole edit for approval (AC 3). Every successful save is in
    the event's History (AC 5)."""

    def list_mine(self, db: Session, coordinator: User) -> list[CoordinatedEventOut]:
        events = db.scalars(
            select(Event)
            .where(Event.coordinator_id == coordinator.id, Event.status.in_(COORDINATED_STATUSES))
            .order_by(Event.start_at, Event.id)
        ).all()
        return [self._summary(event) for event in events]

    def details(self, db: Session, coordinator: User, event_id: uuid.UUID) -> EventDetailsOut:
        return self._details(db, self._coordinated(db, coordinator, event_id))

    def edit(
        self, db: Session, coordinator: User, event_id: uuid.UUID, body: EventEditWrite, now: datetime
    ) -> tuple[EventEditOut, int]:
        """The response and its status: 200 when saved (or nothing changed), 202 when awaiting approval."""
        # FOR UPDATE: a second edit, or a status change, waits for this one and then sees it.
        event = self._coordinated(db, coordinator, event_id, lock=True)
        if event.status != EventStatus.PLANNING:
            raise DomainError(409, "EVENT_NOT_EDITABLE", status=event.status.value)
        cleaned = _clean(body.model_dump(exclude_unset=True), event)

        changes = [
            (field, getattr(event, field), cleaned[field])
            for field in EDIT_FIELDS
            if field in cleaned and cleaned[field] != getattr(event, field)
        ]
        if not changes:
            return EventEditOut(outcome="saved", message=NOTHING_CHANGED_MESSAGE, event=self._details(db, event), change_request=None), 200

        critical = [field for field, _, _ in changes if field in CRITICAL_FIELDS]
        request = None
        if critical:
            # DECISION-PENDING: D84 — the whole edit waits, non-critical fields included, so the event keeps every
            # previous value.
            request = EventChangeRequest(
                event_id=event.id,
                requested_by_user_id=coordinator.id,
                status=ChangeRequestStatus.PENDING_APPROVAL,
                changes=[{"field": f, "old_value": _json(old), "new_value": _json(new)} for f, old, new in changes],
            )
            db.add(request)
            db.flush()
        else:
            for field, _, new in changes:
                setattr(event, field, new)

        # DECISION-PENDING: D85 — a critical edit is a successful save too, so it's logged, tied to its
        # change request. Who approves one (and so what then changes the event) isn't decided.
        for field, old, new in changes:
            db.add(
                EventAuditEntry(
                    event_id=event.id,
                    user_id=coordinator.id,
                    field_name=field,
                    previous_value=_json(old),
                    new_value=_json(new),
                    change_request_id=request.id if request else None,
                    created_at=now,
                )
            )
        db.flush()
        if request is not None:
            db.refresh(request)
            result = EventEditOut(
                outcome="pending_approval",
                message=_pending_message(critical),
                event=self._details(db, event),
                change_request=_change_request_out(request),
            )
        else:
            result = EventEditOut(outcome="saved", message=SAVED_MESSAGE, event=self._details(db, event), change_request=None)
        db.commit()
        return result, 202 if request is not None else 200

    def history(self, db: Session, coordinator: User, event_id: uuid.UUID) -> list[AuditEntryOut]:
        """AC 5: newest first; entries from one save keep the order their fields were written in."""
        event = self._coordinated(db, coordinator, event_id)
        entries = db.scalars(
            select(EventAuditEntry)
            .where(EventAuditEntry.event_id == event.id)
            .order_by(EventAuditEntry.created_at.desc(), EventAuditEntry.seq.desc())
        ).all()
        return [
            AuditEntryOut(
                id=entry.id,
                field=entry.field_name,
                previous_value=entry.previous_value,
                new_value=entry.new_value,
                user=CoordinatorOut.model_validate(entry.user),
                created_at=entry.created_at,
                change_request_id=entry.change_request_id,
                change_request_status=entry.change_request.status if entry.change_request else None,
            )
            for entry in entries
        ]

    def _coordinated(self, db: Session, coordinator: User, event_id: uuid.UUID, lock: bool = False) -> Event:
        """The event, if this user is its assigned coordinator (D48) and it's past the request stage; else 404."""
        query = select(Event).where(Event.id == event_id)
        event = db.scalars(query.with_for_update() if lock else query).one_or_none()
        if event is None or event.status not in COORDINATED_STATUSES or not is_assigned_coordinator(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        return event

    def _summary(self, event: Event) -> CoordinatedEventOut:
        return CoordinatedEventOut(
            id=event.id,
            name=event.name,
            status=event.status,
            editable=event.status == EventStatus.PLANNING,
            start_at=event.start_at,
            end_at=event.end_at,
        )

    def _details(self, db: Session, event: Event) -> EventDetailsOut:
        pending = db.scalars(
            select(EventChangeRequest)
            .where(EventChangeRequest.event_id == event.id, EventChangeRequest.status == ChangeRequestStatus.PENDING_APPROVAL)
            .order_by(EventChangeRequest.created_at.desc(), EventChangeRequest.id)
        ).all()
        return EventDetailsOut(
            **self._summary(event).model_dump(),
            request_reference=event.request_reference,
            event_category=event.event_category,
            purpose=event.purpose,
            room_layout_preference=event.room_layout_preference,
            accessibility_needs=event.accessibility_needs,
            equipment_needs=event.equipment_needs,
            join_link=event.join_link,
            capacity=event.capacity,
            expected_attendees=event.expected_attendees,
            delivery_mode=event.delivery_mode,
            venue_name=event.venue_name,
            room_number=event.room_number,
            pending_change_requests=[_change_request_out(request) for request in pending],
        )


event_edit_service = EventEditService()
