import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event, EventStatus
from app.event.request_schemas import EventRequestOut, EventRequestWrite
from app.user.models import User, UserRole

EVENT_TIMEZONE = ZoneInfo("Asia/Singapore")

REQUIRED_FIELDS = (
    "name",
    "event_category",
    "purpose",
    "preferred_dates",
    "preferred_start_time",
    "preferred_end_time",
    "expected_attendees",
)


def format_request_reference(year: int, sequence: int) -> str:
    return f"ER-{year}-{sequence:06d}"


class EventRequestService:
    def create_draft(
        self, db: Session, owner: User, fields: EventRequestWrite
    ) -> EventRequestOut:
        self._validate_save_fields(fields)
        event = Event(
            **fields.model_dump(),
            status=EventStatus.DRAFT,
            registration_enabled=False,
            created_by_user_id=owner.id,
        )
        db.add(event)
        db.flush()
        result = EventRequestOut.model_validate(event)
        db.commit()
        return result

    def list_mine(self, db: Session, owner: User) -> list[EventRequestOut]:
        events = db.scalars(
            select(Event)
            .where(Event.created_by_user_id == owner.id)
            .order_by(Event.created_at.desc(), Event.id)
        ).all()
        return [EventRequestOut.model_validate(event) for event in events]

    def get(self, db: Session, request_id: uuid.UUID, reader: User) -> EventRequestOut:
        event = db.get(Event, request_id)
        if event is None or not self._can_read(event, reader):
            raise DomainError(404, "NOT_FOUND")
        return EventRequestOut.model_validate(event)

    def update_draft(
        self,
        db: Session,
        request_id: uuid.UUID,
        owner: User,
        fields: EventRequestWrite,
    ) -> EventRequestOut:
        event = self._owned_event(db, request_id, owner)
        if event.status != EventStatus.DRAFT:
            raise DomainError(409, "EVENT_REQUEST_LOCKED")

        values = fields.model_dump(exclude_unset=True)
        self._validate_save_values(values)
        for field_name, value in values.items():
            setattr(event, field_name, value)

        db.flush()
        result = EventRequestOut.model_validate(event)
        db.commit()
        return result

    def submit(
        self, db: Session, request_id: uuid.UUID, owner: User, now: datetime
    ) -> EventRequestOut:
        event = self._owned_event(db, request_id, owner)
        if event.status != EventStatus.DRAFT:
            raise DomainError(409, "EVENT_REQUEST_LOCKED")

        self._validate_submission(event, now)
        event.preferred_dates = sorted(event.preferred_dates or [])
        sequence = db.scalar(text("SELECT nextval('event_request_reference_seq')"))
        if sequence is None:
            raise RuntimeError("event request reference sequence returned no value")
        local_now = now.astimezone(EVENT_TIMEZONE)
        event.status = EventStatus.SUBMITTED
        event.submitted_by_user_id = owner.id
        event.submitted_at = now
        event.request_reference = format_request_reference(local_now.year, sequence)

        db.flush()
        result = EventRequestOut.model_validate(event)
        db.commit()
        return result

    def _owned_event(self, db: Session, request_id: uuid.UUID, owner: User) -> Event:
        event = db.scalars(
            select(Event).where(Event.id == request_id).with_for_update()
        ).one_or_none()
        if event is None or event.created_by_user_id != owner.id:
            raise DomainError(404, "NOT_FOUND")
        return event

    def _can_read(self, event: Event, reader: User) -> bool:
        if event.created_by_user_id == reader.id:
            return True
        if event.status == EventStatus.DRAFT:
            return False
        # DECISION-PENDING: SCRUM-20 — submitted requests are visible to coordinators and
        # operations managers so US8/US10 can proceed; confirm this access policy with the team.
        request_statuses = (
            EventStatus.SUBMITTED,
            EventStatus.UNDER_REVIEW,
            EventStatus.AWAITING_CLARIFICATION,
            EventStatus.APPROVED,
            EventStatus.REJECTED,
        )
        return (
            event.status in request_statuses
            and reader.role in (UserRole.COORDINATOR, UserRole.OPERATIONS_MANAGER)
        )

    def _validate_save_fields(self, fields: EventRequestWrite) -> None:
        self._validate_save_values(fields.model_dump())

    def _validate_save_values(self, values: dict[str, object]) -> None:
        if values.get("expected_attendees") is not None and values["expected_attendees"] < 1:
            raise DomainError(422, "INVALID_EVENT_REQUEST", fields=["expected_attendees"])

    def _validate_submission(self, event: Event, now: datetime) -> None:
        missing = []
        for field_name in REQUIRED_FIELDS:
            value = getattr(event, field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field_name)
        if event.preferred_dates is not None and not event.preferred_dates:
            missing.append("preferred_dates")
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)

        invalid_fields: list[str] = []
        dates = event.preferred_dates or []
        if any(preferred_date < now.astimezone(EVENT_TIMEZONE).date() for preferred_date in dates):
            invalid_fields.append("preferred_dates")
        if len(set(dates)) != len(dates) and "preferred_dates" not in invalid_fields:
            invalid_fields.append("preferred_dates")
        if event.expected_attendees is not None and event.expected_attendees < 1:
            invalid_fields.append("expected_attendees")
        if (
            event.preferred_start_time is not None
            and event.preferred_end_time is not None
            and event.preferred_start_time >= event.preferred_end_time
        ):
            invalid_fields.append("preferred_start_time")
        if invalid_fields:
            raise DomainError(422, "INVALID_EVENT_REQUEST", fields=invalid_fields)


event_request_service = EventRequestService()