import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine
from app.event.assignment_service import MISSING_NAME, MISSING_REFERENCE
from app.event.models import DeliveryMode, Event, EventStatus
from app.event.request_schemas import EventRequestOut, ReadinessItemOut, ReadinessOut
from app.notification.service import Notifier
from app.user.models import User
from app.venue.models import LIVE_BOOKING_STATUSES, Venue, VenueBooking, VenueBookingStatus

logger = logging.getLogger(__name__)

# US18 AC 5: only an event still being arranged can be confirmed. Cancelled, Rejected and an
# already Confirmed event are refused, and so is anything not yet approved. DECISION-PENDING: D56 —
# Approved counts as well as Planning, because nothing moves an approved request on to Planning (D53).
CONFIRMABLE_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING)
# The statuses an event's coordinator works it in, so the readiness list shows in each (widens D11).
WORKING_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.PREPARATION)


class ConfirmationService:
    """SCRUM-85 (US18): the assigned coordinator confirms an event once its arrangements are ready, then
    moves it on to Preparation."""

    def readiness(self, db: Session, request_id: uuid.UUID, coordinator: User) -> ReadinessOut:
        event = self._assigned(db, request_id, coordinator, lock=False)
        if event.status not in WORKING_STATUSES:
            raise DomainError(409, "CONFIRMATION_NOT_ALLOWED", status=event.status.value)
        return self._readiness(db, event, lock=False)[0]

    def confirm(
        self, db: Session, request_id: uuid.UUID, coordinator: User, now: datetime, notifier: Notifier
    ) -> EventRequestOut:
        event = self._assigned(db, request_id, coordinator, lock=True)
        if event.status not in CONFIRMABLE_STATUSES:
            raise DomainError(409, "CONFIRMATION_NOT_ALLOWED", status=event.status.value)
        # AC 1, 5: no override. The bookings and lines are locked with the event, so a Venue staff
        # decision can't land between this check and the status change.
        readiness, approved = self._readiness(db, event, lock=True)
        if not readiness.ready:
            raise DomainError(
                409,
                "EVENT_NOT_READY",
                outstanding=[item.model_dump() for item in readiness.items if not item.complete],
                items=[item.model_dump() for item in readiness.items],
            )

        starts_at = min(booking.starts_at for booking, _ in approved)
        ends_at = max(booking.ends_at for booking, _ in approved)
        venues = list(dict.fromkeys(venue.name for _, venue in approved))
        self._fill_final_fields(event, approved, starts_at, ends_at, venues)
        event.status = EventStatus.CONFIRMED
        event.confirmed_at = now
        event.confirmed_by_user_id = coordinator.id
        db.flush()
        db.refresh(event, ["coordinator", "decided_by"])
        result = EventRequestOut.model_validate(event)
        notice = (event.created_by_user_id, event.request_reference, event.name, starts_at, ends_at, venues)
        db.commit()

        self._notify(db, notifier, event.id, *notice)
        return result

    def start_preparation(self, db: Session, request_id: uuid.UUID, coordinator: User) -> EventRequestOut:
        """AC 6: a Confirmed event moves to Preparation, which is when Venue staff and Technical support
        preparation updates open. Those updates don't exist yet, so nothing else changes here."""
        event = self._assigned(db, request_id, coordinator, lock=True)
        if event.status != EventStatus.CONFIRMED:
            raise DomainError(409, "PREPARATION_NOT_ALLOWED", status=event.status.value)
        event.status = EventStatus.PREPARATION
        db.flush()
        db.refresh(event, ["coordinator", "decided_by"])
        result = EventRequestOut.model_validate(event)
        db.commit()
        return result

    def _assigned(self, db: Session, request_id: uuid.UUID, coordinator: User, *, lock: bool) -> Event:
        query = select(Event).where(Event.id == request_id)
        event = db.scalars(query.with_for_update() if lock else query).one_or_none()
        # D48: only the event's assigned coordinator. Anyone else's, an unassigned event, a draft or an
        # unknown id is 404, never 403, as for other people's records (§1a).
        if event is None or event.status == EventStatus.DRAFT or event.coordinator_id != coordinator.id:
            raise DomainError(404, "NOT_FOUND")
        return event

    def _readiness(
        self, db: Session, event: Event, *, lock: bool
    ) -> tuple[ReadinessOut, list[tuple[VenueBooking, Venue]]]:
        """AC 1, 2: each live venue booking approved, the equipment lines approved, the safety check
        approved. Rejected and withdrawn bookings and rejected lines are not required. Also returns the
        approved bookings, which confirming turns into the event's date, time and venues."""
        bookings_query = (
            select(VenueBooking, Venue)
            .join(Venue, Venue.id == VenueBooking.venue_id)
            .where(VenueBooking.event_id == event.id, VenueBooking.status.in_(LIVE_BOOKING_STATUSES))
            .order_by(VenueBooking.starts_at, VenueBooking.reference)
        )
        if lock:
            bookings_query = bookings_query.with_for_update(of=VenueBooking)
        bookings = [(booking, venue) for booking, venue in db.execute(bookings_query).all()]

        items: list[ReadinessItemOut] = []
        for booking, venue in bookings:
            approved = booking.status == VenueBookingStatus.APPROVED
            items.append(
                ReadinessItemOut(
                    kind="venue",
                    name=venue.name,
                    complete=approved,
                    detail=(
                        f"Booking {booking.reference} is approved."
                        if approved
                        else f"Booking {booking.reference} is waiting for Venue staff to approve it."
                    ),
                )
            )
        if not bookings:
            # DECISION-PENDING: D56 — a request has no delivery mode yet, so every event needs a venue.
            items.append(
                ReadinessItemOut(kind="venue", name="Venue", complete=False, detail="No venue has been requested yet.")
            )

        items.append(self._equipment_item(db, event, lock))
        safety_done = event.safety_approved_at is not None
        items.append(
            ReadinessItemOut(
                kind="safety",
                name="Safety check",
                complete=safety_done,
                detail="Approved by the Safety Officer." if safety_done else "Waiting for the Safety Officer's approval.",
            )
        )
        approved_bookings = [(b, v) for b, v in bookings if b.status == VenueBookingStatus.APPROVED]
        return ReadinessOut(ready=all(item.complete for item in items), items=items), approved_bookings

    def _equipment_item(self, db: Session, event: Event, lock: bool) -> ReadinessItemOut:
        query = select(EquipmentRequestLine).where(
            EquipmentRequestLine.event_id == event.id, EquipmentRequestLine.status != EquipmentLineStatus.REJECTED
        )
        lines = db.scalars(query.with_for_update() if lock else query).all()
        pending = sum(1 for line in lines if line.status == EquipmentLineStatus.PENDING)
        if not lines:
            return ReadinessItemOut(kind="equipment", name="Equipment", complete=True, detail="No equipment was requested.")
        if pending:
            return ReadinessItemOut(
                kind="equipment",
                name="Equipment",
                complete=False,
                detail=f"{pending} of {len(lines)} equipment {'line is' if len(lines) == 1 else 'lines are'}"
                " waiting for Tech support to approve.",
            )
        return ReadinessItemOut(kind="equipment", name="Equipment", complete=True, detail="Every equipment line is approved.")

    def _fill_final_fields(
        self,
        event: Event,
        approved: list[tuple[VenueBooking, Venue]],
        starts_at: datetime,
        ends_at: datetime,
        venues: list[str],
    ) -> None:
        """A request has no date, capacity or delivery mode of its own (events_final_fields_required), so
        a confirmed event takes them from what was arranged: its approved bookings' span and venue(s),
        its expected attendance. Anything the event already holds is kept."""
        event.start_at = event.start_at or starts_at
        event.end_at = event.end_at or ends_at
        if event.capacity is None:
            event.capacity = event.expected_attendees or max(booking.expected_attendees for booking, _ in approved)
        event.delivery_mode = event.delivery_mode or DeliveryMode.IN_PERSON
        event.venue_name = event.venue_name or ", ".join(venues)

    def _notify(
        self,
        db: Session,
        notifier: Notifier,
        request_id: uuid.UUID,
        organiser_id: uuid.UUID | None,
        request_reference: str | None,
        event_name: str | None,
        starts_at: datetime,
        ends_at: datetime,
        venues: list[str],
    ) -> None:
        """AC 4: the organiser hears the event is confirmed, with its date, time and venue(s). Sent after
        the commit, and best effort like the other notices: a failure is logged and never undoes it."""
        try:
            organiser = db.get(User, organiser_id) if organiser_id else None
        except Exception:
            logger.exception("could not look up the organiser of event %s", request_id)
            return
        if organiser is None or not organiser.email:
            logger.warning("could not notify the organiser of event %s: no owner or email", request_id)
            return
        try:
            notifier.event_confirmed(
                email=organiser.email,
                request_reference=request_reference or MISSING_REFERENCE,
                event_name=event_name or MISSING_NAME,
                starts_at=starts_at,
                ends_at=ends_at,
                venues=venues,
            )
        except Exception:
            logger.exception("could not send the confirmation notice for event %s", request_id)


confirmation_service = ConfirmationService()
