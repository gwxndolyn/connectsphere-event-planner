import logging
import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.change_request_schemas import ChangeRequestWrite, OrganiserChangeRequestOut
from app.event.edit_schemas import FieldChangeOut
from app.event.edit_service import _instant
from app.event.edit_service import _json as _edit_json
from app.event.models import ChangeRequestStatus, Event, EventChangeRequest, EventStatus
from app.notification.service import Notifier
from app.user.models import User, UserRole

logger = logging.getLogger(__name__)

# AC 1: Submitted or later, but not Rejected, Cancelled or Completed (and never a draft, which is still edited).
REQUESTABLE_STATUSES = (
    EventStatus.SUBMITTED,
    EventStatus.UNDER_REVIEW,
    EventStatus.AWAITING_CLARIFICATION,
    EventStatus.APPROVED,
    EventStatus.PLANNING,
    EventStatus.CONFIRMED,
)
# Planning onwards, the event has its own start and end (events_final_fields_required); before, only preferences.
PLANNED_STATUSES = (EventStatus.PLANNING, EventStatus.CONFIRMED)

# DECISION-PENDING: D87 — which fields an organiser may ask to change, by stage. AC 1 names date, time, attendance,
# venue and equipment requirements and "other details"; the event's own fields are what can change.
COMMON_FIELDS = (
    "name",
    "event_category",
    "purpose",
    "expected_attendees",
    "room_layout_preference",
    "accessibility_needs",
    "equipment_needs",
)
REQUEST_STAGE_FIELDS = ("preferred_dates", "preferred_start_time", "preferred_end_time")
PLANNED_STAGE_FIELDS = ("start_at", "end_at")
REQUIRED = {"name", "event_category", "purpose", "expected_attendees", "preferred_dates", "preferred_start_time",
            "preferred_end_time", "start_at", "end_at"}
TEXT_FIELDS = {"name", "event_category", "purpose", "room_layout_preference", "accessibility_needs", "equipment_needs"}
LABELS = {
    "name": "Event name",
    "event_category": "Category",
    "purpose": "Purpose",
    "preferred_dates": "Preferred dates",
    "preferred_start_time": "Preferred start time",
    "preferred_end_time": "Preferred end time",
    "start_at": "Start time",
    "end_at": "End time",
    "expected_attendees": "Expected attendance",
    "room_layout_preference": "Room layout",
    "accessibility_needs": "Accessibility needs",
    "equipment_needs": "Equipment needs",
}
REASON_MAX_LENGTH = 1000  # as US17's rejection reason


def _json(value: Any) -> Any:
    """US12's JSON form, plus the request stage's dates and times (ISO strings, dates as a list)."""
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, (date, time)) and not isinstance(value, datetime):
        return value.isoformat()
    return _edit_json(value)


def allowed_fields(event: Event) -> tuple[str, ...]:
    stage = PLANNED_STAGE_FIELDS if event.status in PLANNED_STATUSES else REQUEST_STAGE_FIELDS
    return stage + COMMON_FIELDS


def _dates(value: Any) -> list[date] | None:
    if not isinstance(value, list) or not value:
        return None
    try:
        parsed = [date.fromisoformat(item) for item in value if isinstance(item, str)]
    except ValueError:
        return None
    return sorted(parsed) if len(parsed) == len(value) and len(set(parsed)) == len(parsed) else None


def _time(value: Any) -> time | None:
    if not isinstance(value, str):
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _clean(changes: dict[str, Any], event: Event, today: date) -> dict[str, Any]:
    """Every proposed value checked like the event's own field, each invalid one named with a message."""
    allowed = allowed_fields(event)
    errors: dict[str, str] = {}
    cleaned: dict[str, Any] = {}
    for field, value in changes.items():
        if field not in allowed:
            errors[field] = "This can't be changed at this stage." if field in LABELS else "Unknown field."
            continue
        label = LABELS[field]
        if isinstance(value, str):
            value = value.strip()
        if value is None or value == "" or value == []:
            if field in REQUIRED:
                errors[field] = f"{label} can't be left empty."
            else:
                cleaned[field] = None
            continue
        if field in TEXT_FIELDS:
            if not isinstance(value, str):
                errors[field] = f"{label} must be text."
            elif field == "event_category" and len(value) > 100:
                errors[field] = f"{label} must be at most 100 characters."
            else:
                cleaned[field] = value
        elif field == "expected_attendees":
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                errors[field] = f"{label} must be a whole number of at least 1."
            else:
                cleaned[field] = value
        elif field == "preferred_dates":
            dates = _dates(value)
            if dates is None:
                errors[field] = "Preferred dates must be distinct dates (YYYY-MM-DD)."
            elif dates[0] < today:
                errors[field] = "Preferred dates can't be in the past."
            else:
                cleaned[field] = dates
        elif field in ("preferred_start_time", "preferred_end_time"):
            parsed = _time(value)
            if parsed is None:
                errors[field] = f"{label} must be a time (HH:MM)."
            else:
                cleaned[field] = parsed
        else:  # start_at, end_at
            instant = _instant(value)
            if instant is None:
                errors[field] = f"{label} must be a date and time with its timezone offset."
            else:
                cleaned[field] = instant

    for start_field, end_field in (("preferred_start_time", "preferred_end_time"), ("start_at", "end_at")):
        if start_field not in allowed or start_field in errors or end_field in errors:
            continue
        if start_field not in cleaned and end_field not in cleaned:
            continue
        start = cleaned.get(start_field, getattr(event, start_field))
        end = cleaned.get(end_field, getattr(event, end_field))
        if start is not None and end is not None and end <= start:
            field = end_field if end_field in cleaned else start_field
            errors[field] = "The end must be after the start."
    if errors:
        order = [*LABELS, *sorted(set(errors) - set(LABELS))]
        ordered = {field: errors[field] for field in order if field in errors}
        raise DomainError(422, "INVALID_CHANGE_REQUEST", fields=list(ordered), errors=ordered)
    return cleaned


def _out(request: EventChangeRequest, event: Event) -> OrganiserChangeRequestOut:
    return OrganiserChangeRequestOut(
        id=request.id,
        event_id=event.id,
        event_name=event.name,
        request_reference=event.request_reference,
        status=request.status,
        reason=request.reason,
        changes=[FieldChangeOut(**change) for change in request.changes],
        created_at=request.created_at,
    )


class ChangeRequestService:
    """US29a (SCRUM-97): an Organiser asks for a change to their own event after submitting it. The event keeps
    its values (AC 4) until US29b's review."""

    def create(
        self,
        db: Session,
        organiser: User,
        event_id: uuid.UUID,
        body: ChangeRequestWrite,
        now: datetime,
        notifier: Notifier,
    ) -> OrganiserChangeRequestOut:
        # FOR SHARE: a status change (a cancellation, a decision) waits until this request is in.
        event = db.scalars(select(Event).where(Event.id == event_id).with_for_update(read=True)).one_or_none()
        # Someone else's event is 404 (§1a), and so is a draft: it's still the organiser's to edit.
        if event is None or event.created_by_user_id != organiser.id or event.status == EventStatus.DRAFT:
            raise DomainError(404, "NOT_FOUND")
        if event.status not in REQUESTABLE_STATUSES:
            raise DomainError(409, "CHANGE_NOT_ALLOWED", status=event.status.value)

        reason = (body.reason or "").strip()
        if not body.changes and not reason:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=["changes", "reason"])
        if not body.changes:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=["changes"])
        if not reason:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=["reason"])
        if len(reason) > REASON_MAX_LENGTH:
            raise DomainError(422, "INVALID_CHANGE_REQUEST", fields=["reason"],
                              errors={"reason": f"The reason must be at most {REASON_MAX_LENGTH} characters."})

        cleaned = _clean(body.changes, event, now.date())
        changes = [
            {"field": field, "old_value": _json(getattr(event, field)), "new_value": _json(cleaned[field])}
            for field in allowed_fields(event)
            if field in cleaned and _json(cleaned[field]) != _json(getattr(event, field))
        ]
        if not changes:
            raise DomainError(422, "NO_CHANGES", message="Every proposed value is the same as the current one.")

        request = EventChangeRequest(
            event_id=event.id,
            requested_by_user_id=organiser.id,
            status=ChangeRequestStatus.PENDING_APPROVAL,
            changes=changes,
            reason=reason,
            created_at=now,
        )
        db.add(request)
        db.flush()
        result = _out(request, event)
        db.commit()

        self._notify(db, notifier, event, organiser, [c["field"] for c in changes], reason)
        return result

    def list_mine(self, db: Session, organiser: User, event_id: uuid.UUID | None = None) -> list[OrganiserChangeRequestOut]:
        """AC 6: the organiser's own requests, newest first, optionally for one event."""
        query = (
            select(EventChangeRequest, Event)
            .join(Event, Event.id == EventChangeRequest.event_id)
            .where(EventChangeRequest.requested_by_user_id == organiser.id, Event.created_by_user_id == organiser.id)
        )
        if event_id is not None:
            query = query.where(Event.id == event_id)
        rows = db.execute(query.order_by(EventChangeRequest.created_at.desc(), EventChangeRequest.id)).all()
        return [_out(request, event) for request, event in rows]

    def _notify(
        self, db: Session, notifier: Notifier, event: Event, organiser: User, fields: list[str], reason: str
    ) -> None:
        """AC 5, after the commit and best effort, as the other notices: a failure is logged and the request stands."""
        try:
            coordinator = db.get(User, event.coordinator_id) if event.coordinator_id else None
            if coordinator is not None and coordinator.is_active:
                recipients, to_lead = [coordinator], False
            else:
                # DECISION-PENDING: D88 — nobody is assigned (a Submitted event, D27), so every active Lead hears
                # instead, as when a request joins the queue (D28).
                recipients = db.scalars(
                    select(User)
                    .where(User.roles.any(UserRole.COORDINATOR_LEAD), User.is_active.is_(True))
                    .order_by(User.email)
                ).all()
                to_lead = True
            if not recipients:
                logger.warning("could not notify anyone about a change request on event %s: no one is active", event.id)
                return
        except Exception:
            logger.exception("could not look up who to notify about a change request on event %s", event.id)
            return
        for recipient in recipients:
            try:
                notifier.change_requested(
                    email=recipient.email,
                    event_id=event.id,
                    event_name=event.name or event.request_reference or str(event.id),
                    organiser_name=organiser.display_name,
                    fields=fields,
                    reason=reason,
                    to_lead=to_lead,
                )
            except Exception:
                logger.exception("could not notify %s about a change request on event %s", recipient.id, event.id)


change_request_service = ChangeRequestService()
