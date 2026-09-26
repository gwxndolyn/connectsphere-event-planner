from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.event.models import Event, EventRegistrationField, EventStatus
from app.event.schemas import AvailableEventOut, AvailableEventsResponse, RegistrationFieldOut
from app.registration.models import ACTIVE_STATUSES, Registration
from app.registration.service import registration_service
from app.user.models import Attendee


class EventService:
    def health(self) -> str:
        return "event service is up"

    def list_available(self, db: Session, attendee: Attendee, now: datetime) -> AvailableEventsResponse:
        """SCRUM-25: events an attendee may register for right now (TC-US3-01)."""
        events = db.scalars(
            select(Event)
            .where(
                Event.status == EventStatus.CONFIRMED,
                Event.registration_enabled.is_(True),
                or_(Event.registration_opens_at.is_(None), Event.registration_opens_at <= now),
                or_(Event.registration_closes_at.is_(None), Event.registration_closes_at > now),
                Event.end_at > now,
            )
            .order_by(Event.start_at)
        ).all()

        if not events:
            return AvailableEventsResponse(events=[])

        event_ids = [event.id for event in events]

        fields_by_event: dict[object, list[EventRegistrationField]] = {}
        for field in db.scalars(
            select(EventRegistrationField)
            .where(EventRegistrationField.event_id.in_(event_ids))
            .order_by(EventRegistrationField.sort_order)
        ):
            fields_by_event.setdefault(field.event_id, []).append(field)

        registered_event_ids = set(
            db.scalars(
                select(Registration.event_id).where(
                    Registration.event_id.in_(event_ids),
                    Registration.attendee_id == attendee.id,
                    Registration.status.in_(ACTIVE_STATUSES),
                )
            )
        )

        out = []
        for event in events:
            seats_remaining = registration_service.seats_remaining(db, event, now)
            out.append(
                AvailableEventOut(
                    id=event.id,
                    name=event.name,
                    start_at=event.start_at,
                    end_at=event.end_at,
                    delivery_mode=event.delivery_mode,
                    venue_name=event.venue_name,
                    join_link=event.join_link,
                    capacity=event.capacity,
                    seats_remaining=max(seats_remaining, 0),
                    is_full=seats_remaining <= 0,
                    already_registered=event.id in registered_event_ids,
                    registration_fields=[
                        RegistrationFieldOut(
                            field_key=field.field_key,
                            label=field.label,
                            field_type=field.field_type,
                            options=field.options,
                            required=field.required,
                        )
                        for field in fields_by_event.get(event.id, [])
                    ],
                )
            )
        return AvailableEventsResponse(events=out)


event_service = EventService()
