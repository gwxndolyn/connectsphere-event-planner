import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.equipment.models import EquipmentReservation, TechStaffAssignment
from app.event.cancellation_schemas import CancellationOut, CancellationWrite
from app.event.models import CancellationStatus, Event, EventCancellation, EventStatus
from app.event.request_schemas import CoordinatorOut
from app.event.self_decision import refuse_self_decision
from app.notification.service import CancellationRecipient, Notifier
from app.registration.models import ACTIVE_STATUSES, Registration, RegistrationStatus
from app.user.models import User, UserRole
from app.venue.models import LIVE_BOOKING_STATUSES, VenueBooking, VenueBookingStatus

logger = logging.getLogger(__name__)

# AC 1: from approval until the start. Approved counts as well as Planning because nothing moves an approved event
# on to Planning (D53), as US18 found (D86). Before approval a request is rejected (US17), not cancelled; Rejected,
# Cancelled (AC 4) and Completed (AC 7) are over.
CANCELLABLE_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.PREPARATION)
REASON_MAX_LENGTH = 1000  # as US17's rejection reason and US29a's change request reason
EVENT_TIMEZONE = ZoneInfo("Asia/Singapore")


def _starts_at(event: Event, first_booking: datetime | None) -> datetime | None:
    """When the event starts, for AC 7. Its own start once planned. An Approved request has none (D86), so:
    DECISION-PENDING: D101 — its earliest live venue booking, which places it; with no booking, its last preferred
    date at its preferred start time, Singapore time (D9), by when it has started whichever date it's on. None if
    it has neither."""
    if event.start_at is not None:
        return event.start_at
    if first_booking is not None:
        return first_booking
    if not event.preferred_dates or event.preferred_start_time is None:
        return None
    return datetime.combine(max(event.preferred_dates), event.preferred_start_time, tzinfo=EVENT_TIMEZONE)


def _reason(body: CancellationWrite) -> str:
    reason = (body.reason or "").strip()
    if not reason:
        raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=["reason"])
    if len(reason) > REASON_MAX_LENGTH:
        raise DomainError(
            422,
            "INVALID_CANCELLATION",
            fields=["reason"],
            errors={"reason": f"The reason must be at most {REASON_MAX_LENGTH} characters."},
        )
    return reason


def _person(user: User) -> CoordinatorOut:
    return CoordinatorOut.model_validate(user)


def _out(row: EventCancellation, event: Event) -> CancellationOut:
    return CancellationOut(
        id=row.id,
        event_id=event.id,
        event_name=event.name,
        request_reference=event.request_reference,
        event_status=event.status,
        status=row.status,
        reason=row.reason,
        requested_by=_person(row.requested_by),
        requested_at=row.requested_at,
        decided_by=_person(row.decided_by) if row.decided_by else None,
        decided_at=row.decided_at,
        rejection_reason=row.rejection_reason,
        direct=row.direct,
    )


@dataclass
class _Notice:
    """Who to tell once the cancellation commits (AC 6), read inside the transaction."""

    event_id: uuid.UUID
    event_name: str
    reason: str
    recipients: list[tuple[str, CancellationRecipient]]


class CancellationService:
    """US9 (SCRUM-12): an Organiser asks to cancel their event and the assigned coordinator decides (AC 1, 2), or the
    coordinator cancels it directly (AC 3). Cancelling can't be undone (AC 4), releases the event's venues and
    equipment (AC 5) and tells everyone involved (AC 6)."""

    def request(
        self, db: Session, organiser: User, event_id: uuid.UUID, body: CancellationWrite, now: datetime,
        notifier: Notifier,
    ) -> CancellationOut:
        event = self._lock(db, event_id)
        # Someone else's event is 404 (§1a), and so is a draft: it's still the organiser's to edit or delete.
        if event is None or event.created_by_user_id != organiser.id or event.status == EventStatus.DRAFT:
            raise DomainError(404, "NOT_FOUND")
        self._check_cancellable(db, event, now)
        reason = _reason(body)
        self._refuse_if_pending(db, event)

        row = EventCancellation(event_id=event.id, requested_by_user_id=organiser.id, reason=reason, requested_at=now)
        db.add(row)
        db.flush()
        db.refresh(row, ["requested_by"])
        result = _out(row, event)
        coordinator_id = event.coordinator_id
        db.commit()

        self._notify_requested(db, notifier, event, organiser, coordinator_id, reason)
        return result

    def cancel(
        self, db: Session, coordinator: User, event_id: uuid.UUID, body: CancellationWrite, now: datetime,
        notifier: Notifier,
    ) -> CancellationOut:
        """AC 3: the assigned coordinator cancels the event themselves, with a reason."""
        event = self._lock_coordinated(db, event_id, coordinator, bookings=True)
        self._check_cancellable(db, event, now)
        reason = _reason(body)
        # The organiser's waiting request is the coordinator's to decide: approving it cancels the event and keeps
        # who asked (AC 8), where a second, direct cancellation would leave it open (event_cancellations_one_open).
        self._refuse_if_pending(db, event)

        row = EventCancellation(
            event_id=event.id,
            requested_by_user_id=coordinator.id,
            reason=reason,
            status=CancellationStatus.APPROVED,
            requested_at=now,
            decided_by_user_id=coordinator.id,
            decided_at=now,
            direct=True,
        )
        db.add(row)
        return self._cancel(db, notifier, event, row, now)

    def approve(
        self, db: Session, coordinator: User, cancellation_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> CancellationOut:
        """AC 2: approving the organiser's request cancels the event."""
        event, row = self._lock_request(db, cancellation_id, coordinator, bookings=True)
        self._check_pending(row)
        # AC 7: an event that has started or is over is refused, and the request stays pending for a rejection.
        self._check_cancellable(db, event, now)
        row.status = CancellationStatus.APPROVED
        row.decided_by_user_id = coordinator.id
        row.decided_at = now
        return self._cancel(db, notifier, event, row, now)

    def reject(
        self, db: Session, coordinator: User, cancellation_id: uuid.UUID, body: CancellationWrite, now: datetime,
        notifier: Notifier,
    ) -> CancellationOut:
        """AC 2: the event goes ahead. A reason is required (the story owner's choice), as for US17's rejection."""
        event, row = self._lock_request(db, cancellation_id, coordinator)
        rejection_reason = _reason(body)
        self._check_pending(row)
        row.status = CancellationStatus.REJECTED
        row.decided_by_user_id = coordinator.id
        row.decided_at = now
        row.rejection_reason = rejection_reason
        db.flush()
        db.refresh(row, ["requested_by", "decided_by"])
        result = _out(row, event)
        organiser = row.requested_by
        db.commit()

        try:
            notifier.cancellation_rejected(
                email=organiser.email,
                event_id=event.id,
                event_name=self._name(event),
                reason=row.reason,
                rejection_reason=rejection_reason,
            )
        except Exception:
            logger.exception("could not tell %s their cancellation request %s was rejected", organiser.id, row.id)
        return result

    def list_for_event(self, db: Session, reader: User, event_id: uuid.UUID) -> list[CancellationOut]:
        """AC 8: the event's cancellation requests and decisions, newest first, for its organiser and its coordinator."""
        event = db.get(Event, event_id)
        if event is None or event.status == EventStatus.DRAFT or reader.id not in (
            event.created_by_user_id,
            event.coordinator_id if reader.holds(UserRole.COORDINATOR) else None,
        ):
            raise DomainError(404, "NOT_FOUND")
        rows = db.scalars(
            select(EventCancellation)
            .where(EventCancellation.event_id == event.id)
            # A new request can only follow a decision, so at the same instant the undecided one is newer.
            .order_by(
                EventCancellation.requested_at.desc(),
                EventCancellation.decided_at.desc().nulls_first(),
                EventCancellation.id,
            )
        ).all()
        return [_out(row, event) for row in rows]

    def _lock(self, db: Session, event_id: uuid.UUID) -> Event | None:
        # FOR UPDATE: a cancellation and a decision, a confirmation or an edit can't both land.
        return db.scalars(select(Event).where(Event.id == event_id).with_for_update()).one_or_none()

    def _lock_coordinated(self, db: Session, event_id: uuid.UUID, coordinator: User, bookings: bool = False) -> Event:
        if bookings:
            # The event's live bookings before the event itself, the order Venue staff's approve takes them in
            # (booking, then event), so a cancel and an approve wait for each other instead of deadlocking.
            db.scalars(self._live_bookings(event_id).with_for_update()).all()
        event = self._lock(db, event_id)
        # D48: only the event's assigned coordinator. Anyone else's, an unassigned event or a draft is 404 (§1a).
        if event is None or event.status == EventStatus.DRAFT or event.coordinator_id != coordinator.id:
            raise DomainError(404, "NOT_FOUND")
        return event

    def _lock_request(
        self, db: Session, cancellation_id: uuid.UUID, coordinator: User, bookings: bool = False
    ) -> tuple[Event, EventCancellation]:
        found = db.get(EventCancellation, cancellation_id)
        if found is None:
            raise DomainError(404, "NOT_FOUND")
        event = self._lock_coordinated(db, found.event_id, coordinator, bookings)
        row = db.scalars(
            select(EventCancellation)
            .where(EventCancellation.id == cancellation_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        # D51: no one decides a request they made. Before the pending check, so the refusal doesn't depend on it.
        refuse_self_decision(coordinator, created_by_user_id=row.requested_by_user_id)
        return event, row

    def _live_bookings(self, event_id: uuid.UUID):
        return (
            select(VenueBooking)
            .where(VenueBooking.event_id == event_id, VenueBooking.status.in_(LIVE_BOOKING_STATUSES))
            .order_by(VenueBooking.id)
        )

    def _check_cancellable(self, db: Session, event: Event, now: datetime) -> None:
        if event.status not in CANCELLABLE_STATUSES:
            raise DomainError(409, "CANCELLATION_NOT_ALLOWED", status=event.status.value)
        first_booking = db.scalar(
            select(func.min(VenueBooking.starts_at)).where(
                VenueBooking.event_id == event.id, VenueBooking.status.in_(LIVE_BOOKING_STATUSES)
            )
        )
        starts_at = _starts_at(event, first_booking)
        # AC 7: once the event is on, cancelling it is refused.
        if starts_at is not None and now >= starts_at:
            raise DomainError(409, "EVENT_STARTED", starts_at=starts_at.isoformat())

    def _check_pending(self, row: EventCancellation) -> None:
        if row.status != CancellationStatus.PENDING:
            raise DomainError(409, "CANCELLATION_NOT_PENDING", status=row.status.value)

    def _refuse_if_pending(self, db: Session, event: Event) -> None:
        pending = db.scalar(
            select(EventCancellation.id).where(
                EventCancellation.event_id == event.id, EventCancellation.status == CancellationStatus.PENDING
            )
        )
        if pending is not None:
            raise DomainError(409, "CANCELLATION_PENDING", cancellation_id=str(pending))

    def _cancel(
        self, db: Session, notifier: Notifier, event: Event, row: EventCancellation, now: datetime
    ) -> CancellationOut:
        """AC 4, 5: in one transaction the event is Cancelled and its venues and equipment are free again."""
        event.status = EventStatus.CANCELLED
        # Again under the event's lock: a booking requested before it was taken is here now (create locks the event).
        bookings = db.scalars(
            self._live_bookings(event.id).with_for_update().execution_options(populate_existing=True)
        ).all()
        released_approved = any(booking.status == VenueBookingStatus.APPROVED for booking in bookings)
        # D60, D69: every live booking, of every venue, is withdrawn; an approved one keeps its decision (D77).
        for booking in bookings:
            booking.status = VenueBookingStatus.WITHDRAWN
            booking.withdrawn_at = now
            booking.updated_at = now
        # D75 (Calvin's ask on SCRUM-12): releasing a reservation is deleting it.
        db.execute(delete(EquipmentReservation).where(EquipmentReservation.event_id == event.id))
        # TODO(US25): release the event's tentative venue holds here (SCRUM-93 AC 7).
        # Tech support assignments stay (the story owner's choice): D81 already frees the staff of a cancelled event.
        db.flush()
        db.refresh(row, ["requested_by", "decided_by"])
        result = _out(row, event)
        notice = self._recipients(db, event, row, now, released_approved=released_approved)
        db.commit()

        self._send(notifier, notice)
        return result

    def _recipients(
        self, db: Session, event: Event, row: EventCancellation, now: datetime, *, released_approved: bool
    ) -> _Notice:
        """AC 6: the Organiser, Venue staff, Tech support staff and every registered and wait-listed attendee."""
        recipients: list[tuple[str, CancellationRecipient]] = []
        organiser = db.get(User, event.created_by_user_id) if event.created_by_user_id else None
        if organiser is not None:
            recipients.append((organiser.email, "organiser"))
        if released_approved:
            # DECISION-PENDING: D100 — Venue staff aren't assigned to an event, so every active Venue staff member
            # hears when an approved venue is released, as when an approved booking is withdrawn (D69).
            staff = db.scalars(
                select(User)
                .where(User.roles.any(UserRole.VENUE_STAFF), User.is_active.is_(True))
                .order_by(User.email)
            ).all()
            recipients += [(user.email, "venue_staff") for user in staff]
        tech = db.scalars(
            select(User)
            .join(TechStaffAssignment, TechStaffAssignment.staff_user_id == User.id)
            .where(
                TechStaffAssignment.event_id == event.id,
                TechStaffAssignment.unassigned_at.is_(None),
                User.is_active.is_(True),
            )
            .order_by(User.email)
        ).all()
        recipients += [(user.email, "tech_support") for user in tech]
        # Registered, offered a place and wait-listed; not those who withdrew, declined or let an offer lapse, even an
        # offer no read has swept yet (D2): sweeping now would hand the place on just before the cancel.
        attendees = db.scalars(
            select(Registration.attendee_email)
            .where(
                Registration.event_id == event.id,
                Registration.status.in_(ACTIVE_STATUSES),
                or_(
                    Registration.status != RegistrationStatus.OFFERED,
                    Registration.offer_expires_at.is_(None),
                    Registration.offer_expires_at > now,
                ),
            )
            .order_by(Registration.attendee_email)
        ).all()
        recipients += [(email, "attendee") for email in attendees]

        seen: set[str] = set()
        unique = []
        for email, recipient in recipients:
            if email and email.lower() not in seen:
                seen.add(email.lower())
                unique.append((email, recipient))
        return _Notice(event_id=event.id, event_name=self._name(event), reason=row.reason, recipients=unique)

    def _send(self, notifier: Notifier, notice: _Notice) -> None:
        """After the commit and best effort, as the other notices: one failure is logged and the rest still go."""
        for email, recipient in notice.recipients:
            try:
                notifier.event_cancelled(
                    email=email,
                    event_id=notice.event_id,
                    event_name=notice.event_name,
                    reason=notice.reason,
                    recipient=recipient,
                )
            except Exception:
                logger.exception("could not tell %s that event %s is cancelled", recipient, notice.event_id)

    def _notify_requested(
        self, db: Session, notifier: Notifier, event: Event, organiser: User, coordinator_id: uuid.UUID | None,
        reason: str,
    ) -> None:
        """AC 2: the assigned coordinator hears of the request. After the commit; a failure is logged."""
        try:
            coordinator = db.get(User, coordinator_id) if coordinator_id else None
            if coordinator is None or not coordinator.is_active:
                logger.warning("could not tell anyone about the cancellation request on event %s", event.id)
                return
            notifier.cancellation_requested(
                email=coordinator.email,
                event_id=event.id,
                event_name=self._name(event),
                organiser_name=organiser.display_name,
                reason=reason,
            )
        except Exception:
            logger.exception("could not send the cancellation request notice for event %s", event.id)

    def _name(self, event: Event) -> str:
        return event.name or event.request_reference or str(event.id)


cancellation_service = CancellationService()
