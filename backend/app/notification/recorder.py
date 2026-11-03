import logging
import uuid
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.equipment.models import EquipmentRequestLine
from app.event.models import Event
from app.notification.models import Notification
from app.notification.service import (
    AssignmentRecipient,
    BookingDecision,
    CancellationRecipient,
    HoldStage,
    LoggingNotifier,
    Notifier,
    ReassignmentRecipient,
    RequestDecision,
    SafetyOutcome,
    UnavailabilityRecipient,
)
from app.registration.models import Registration
from app.user.models import User
from app.venue.models import VenueBooking

logger = logging.getLogger(__name__)


# TC-X-01: timestamps are stored UTC, and the team and every event are in Singapore, so a sentence that is
# kept as text names the time as the people reading it say it (US31 review).
EVENT_TIMEZONE = ZoneInfo("Asia/Singapore")


def _when(value: datetime) -> str:
    return value.astimezone(EVENT_TIMEZONE).strftime("%a %d %b %Y, %H:%M SGT")


def _dates(values: list[date]) -> str:
    return ", ".join(value.strftime("%d %b %Y") for value in values) or "no dates yet"


def _sentence(text: str, extra: str | None) -> str:
    return f"{text} {extra}" if extra else text


class RecordingNotifier:
    """US31 (SCRUM-107): the Notifier every story already calls, now also keeping each notice as a row for the
    person it was sent to (AC 2, 6). The calls are unchanged: it logs through the notifier it wraps, then
    records. Like the logging, recording is best effort, so a failure here is logged and never undoes the
    change that raised the notice. Most notices are raised after the caller's commit. A waitlist offer is
    not: it goes out inside the withdrawal's transaction, so it is recorded before that commits, and if the
    transaction then rolls back the notification for an offer that never happened stays (D116).

    Recipients are named by email, so the user is found by email; an address no user holds (an attendee who
    never logged in) is logged and skipped. The event is found from whatever the notice carries: its id, its
    request reference, or the booking, equipment line or registration it is about."""

    def __init__(
        self,
        delegate: Notifier,
        session_factory: Callable[[], Session] = SessionLocal,
        *,
        close_sessions: bool = True,
    ) -> None:
        self._delegate = delegate
        self._session_factory = session_factory
        self._close_sessions = close_sessions

    # --- recording ---

    def _record(
        self,
        kind: str,
        *,
        email: str,
        event_name: str | None,
        message: str,
        event_id: uuid.UUID | None = None,
        request_reference: str | None = None,
        booking_id: uuid.UUID | None = None,
        line_id: uuid.UUID | None = None,
        registration_id: uuid.UUID | None = None,
    ) -> None:
        try:
            db = self._session_factory()
        except Exception:
            logger.exception("could not open a session to record the %s notice for %s", kind, email)
            return
        try:
            # Never wait long on a lock the caller holds: a notice is best effort, so give up (and log it)
            # rather than hold the request up.
            db.execute(text("SET LOCAL lock_timeout = '2s'"))
            user = db.scalars(select(User).where(func.lower(User.email) == email.lower())).first()
            if user is None:
                logger.warning("no user holds %s, so the %s notice isn't kept", email, kind)
                return
            resolved = event_id or self._event_of(
                db,
                request_reference=request_reference,
                booking_id=booking_id,
                line_id=line_id,
                registration_id=registration_id,
            )
            db.add(Notification(user_id=user.id, kind=kind, event_id=resolved, event_name=event_name, message=message))
            db.commit()
        except Exception:
            logger.exception("could not record the %s notice for %s", kind, email)
            try:
                db.rollback()
            except Exception:
                logger.exception("could not roll back after failing to record the %s notice", kind)
        finally:
            if self._close_sessions:
                db.close()

    def _event_of(
        self,
        db: Session,
        *,
        request_reference: str | None,
        booking_id: uuid.UUID | None,
        line_id: uuid.UUID | None,
        registration_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if booking_id is not None:
            return db.scalar(select(VenueBooking.event_id).where(VenueBooking.id == booking_id))
        if line_id is not None:
            return db.scalar(select(EquipmentRequestLine.event_id).where(EquipmentRequestLine.id == line_id))
        if registration_id is not None:
            return db.scalar(select(Registration.event_id).where(Registration.id == registration_id))
        if request_reference:
            return db.scalar(select(Event.id).where(Event.request_reference == request_reference))
        return None

    # --- the Notifier ---

    def waitlist_offer(
        self, *, email: str, event_name: str, expires_at: datetime, registration_id: uuid.UUID
    ) -> None:
        self._delegate.waitlist_offer(
            email=email, event_name=event_name, expires_at=expires_at, registration_id=registration_id
        )
        self._record(
            "waitlist_offer",
            email=email,
            event_name=event_name,
            message=f"A place has opened up. Accept it before {_when(expires_at)}.",
            registration_id=registration_id,
        )

    def clarification_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        round: int,
        sections: list[str],
        comment: str,
    ) -> None:
        self._delegate.clarification_requested(
            email=email,
            request_reference=request_reference,
            event_name=event_name,
            round=round,
            sections=sections,
            comment=comment,
        )
        self._record(
            "clarification_requested",
            email=email,
            event_name=event_name,
            message=f"The coordinator asked for clarification on {', '.join(sections)} (round {round}): {comment}",
            request_reference=request_reference,
        )

    def venue_booking_requested(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        self._delegate.venue_booking_requested(
            email=email,
            booking_id=booking_id,
            event_name=event_name,
            venue_name=venue_name,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        self._record(
            "venue_booking_requested",
            email=email,
            event_name=event_name,
            message=f"A booking was requested for {venue_name}, {_when(starts_at)} to {_when(ends_at)}.",
            booking_id=booking_id,
        )

    def venue_booking_decided(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        decision: BookingDecision,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str | None,
        alternative_suggestion: str | None,
    ) -> None:
        self._delegate.venue_booking_decided(
            email=email,
            booking_id=booking_id,
            decision=decision,
            event_name=event_name,
            venue_name=venue_name,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=reason,
            alternative_suggestion=alternative_suggestion,
        )
        message = f"Your booking request for {venue_name}, {_when(starts_at)} to {_when(ends_at)}, was {decision}."
        if reason:
            message += f" Reason: {reason}"
        if alternative_suggestion:
            message += f" Suggested instead: {alternative_suggestion}"
        self._record("venue_booking_decided", email=email, event_name=event_name, message=message, booking_id=booking_id)

    def venue_booking_withdrawn(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> None:
        self._delegate.venue_booking_withdrawn(
            email=email,
            booking_id=booking_id,
            event_name=event_name,
            venue_name=venue_name,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        self._record(
            "venue_booking_withdrawn",
            email=email,
            event_name=event_name,
            message=f"The booking for {venue_name}, {_when(starts_at)} to {_when(ends_at)}, was withdrawn.",
            booking_id=booking_id,
        )

    def request_queued(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        organiser_name: str,
        preferred_dates: list[date],
    ) -> None:
        self._delegate.request_queued(
            email=email,
            request_reference=request_reference,
            event_name=event_name,
            organiser_name=organiser_name,
            preferred_dates=preferred_dates,
        )
        self._record(
            "request_queued",
            email=email,
            event_name=event_name,
            message=f"{organiser_name} submitted request {request_reference} for {_dates(preferred_dates)}. It is waiting to be assigned.",
            request_reference=request_reference,
        )

    def assignment_made(
        self,
        *,
        email: str,
        recipient: AssignmentRecipient,
        request_reference: str,
        event_name: str,
        coordinator_name: str,
        event_dates: list[date],
    ) -> None:
        self._delegate.assignment_made(
            email=email,
            recipient=recipient,
            request_reference=request_reference,
            event_name=event_name,
            coordinator_name=coordinator_name,
            event_dates=event_dates,
        )
        message = (
            f"You were assigned to coordinate request {request_reference} ({_dates(event_dates)})."
            if recipient == "coordinator"
            else f"{coordinator_name} was assigned to coordinate your request {request_reference} ({_dates(event_dates)})."
        )
        self._record(
            "assignment_made", email=email, event_name=event_name, message=message, request_reference=request_reference
        )

    def event_reassigned(
        self,
        *,
        email: str,
        recipient: ReassignmentRecipient,
        request_reference: str,
        event_name: str,
        previous_coordinator_name: str,
        new_coordinator_name: str,
        event_dates: list[date],
        reason: str,
    ) -> None:
        self._delegate.event_reassigned(
            email=email,
            recipient=recipient,
            request_reference=request_reference,
            event_name=event_name,
            previous_coordinator_name=previous_coordinator_name,
            new_coordinator_name=new_coordinator_name,
            event_dates=event_dates,
            reason=reason,
        )
        if recipient == "new_coordinator":
            message = f"{request_reference} was reassigned to you from {previous_coordinator_name}. Reason: {reason}"
        elif recipient == "previous_coordinator":
            message = f"{request_reference} was reassigned from you to {new_coordinator_name}. Reason: {reason}"
        else:
            message = f"Your request {request_reference} now has a new coordinator, {new_coordinator_name}. Reason: {reason}"
        self._record(
            "event_reassigned", email=email, event_name=event_name, message=message, request_reference=request_reference
        )

    def transfer_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        coordinator_name: str,
        reason: str,
    ) -> None:
        self._delegate.transfer_requested(
            email=email,
            request_reference=request_reference,
            event_name=event_name,
            coordinator_name=coordinator_name,
            reason=reason,
        )
        self._record(
            "transfer_requested",
            email=email,
            event_name=event_name,
            message=f"{coordinator_name} asked to transfer request {request_reference}. Reason: {reason}",
            request_reference=request_reference,
        )

    def equipment_line_reviewed(
        self,
        *,
        email: str,
        line_id: uuid.UUID,
        event_name: str,
        equipment_type: str,
        quantity: int,
        decision: str,
        note: str | None,
    ) -> None:
        self._delegate.equipment_line_reviewed(
            email=email,
            line_id=line_id,
            event_name=event_name,
            equipment_type=equipment_type,
            quantity=quantity,
            decision=decision,
            note=note,
        )
        self._record(
            "equipment_line_reviewed",
            email=email,
            event_name=event_name,
            message=_sentence(f"Your request for {quantity} × {equipment_type} was {decision}.", f"Note: {note}" if note else None),
            line_id=line_id,
        )

    def request_decided(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        decision: RequestDecision,
        reason: str | None,
    ) -> None:
        self._delegate.request_decided(
            email=email,
            request_reference=request_reference,
            event_name=event_name,
            decision=decision,
            reason=reason,
        )
        self._record(
            "request_decided",
            email=email,
            event_name=event_name,
            message=_sentence(f"Your request {request_reference} was {decision}.", f"Reason: {reason}" if reason else None),
            request_reference=request_reference,
        )

    def tech_staff_assigned(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        starts_at: datetime,
        ends_at: datetime,
        venue_name: str | None,
        location: str | None,
        equipment: list[str],
        equipment_needs: str | None,
    ) -> None:
        self._delegate.tech_staff_assigned(
            email=email,
            event_id=event_id,
            event_name=event_name,
            starts_at=starts_at,
            ends_at=ends_at,
            venue_name=venue_name,
            location=location,
            equipment=equipment,
            equipment_needs=equipment_needs,
        )
        where = f" at {venue_name}" if venue_name else ""
        gear = f" Equipment: {', '.join(equipment)}." if equipment else ""
        self._record(
            "tech_staff_assigned",
            email=email,
            event_name=event_name,
            message=f"You were assigned to support the event, {_when(starts_at)} to {_when(ends_at)}{where}.{gear}",
            event_id=event_id,
        )

    def event_confirmed(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        starts_at: datetime,
        ends_at: datetime,
        venues: list[str],
    ) -> None:
        self._delegate.event_confirmed(
            email=email,
            request_reference=request_reference,
            event_name=event_name,
            starts_at=starts_at,
            ends_at=ends_at,
            venues=venues,
        )
        where = f" at {', '.join(venues)}" if venues else ""
        self._record(
            "event_confirmed",
            email=email,
            event_name=event_name,
            message=f"The event is confirmed for {_when(starts_at)} to {_when(ends_at)}{where}.",
            request_reference=request_reference,
        )

    def safety_review_decided(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        outcome: SafetyOutcome,
        comments: str | None,
        issues: list[str],
    ) -> None:
        self._delegate.safety_review_decided(
            email=email,
            request_reference=request_reference,
            event_name=event_name,
            outcome=outcome,
            comments=comments,
            issues=issues,
        )
        message = f"The Safety Officer {outcome} the safety arrangement."
        if issues:
            message += f" Flagged: {', '.join(issues)}."
        if comments:
            message += f" Comments: {comments}"
        self._record(
            "safety_review_decided", email=email, event_name=event_name, message=message, request_reference=request_reference
        )

    def safety_changes_requested(
        self,
        *,
        email: str,
        request_reference: str,
        event_name: str,
        comments: str,
        areas: list[str],
        issues: list[str],
    ) -> None:
        self._delegate.safety_changes_requested(
            email=email,
            request_reference=request_reference,
            event_name=event_name,
            comments=comments,
            areas=areas,
            issues=issues,
        )
        message = f"The Safety Officer asked for changes to {', '.join(areas)}."
        if issues:
            message += f" Flagged: {', '.join(issues)}."
        message += f" Comments: {comments}"
        self._record(
            "safety_changes_requested",
            email=email,
            event_name=event_name,
            message=message,
            request_reference=request_reference,
        )

    def change_requested(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        organiser_name: str,
        fields: list[str],
        reason: str,
        to_lead: bool,
    ) -> None:
        self._delegate.change_requested(
            email=email,
            event_id=event_id,
            event_name=event_name,
            organiser_name=organiser_name,
            fields=fields,
            reason=reason,
            to_lead=to_lead,
        )
        self._record(
            "change_requested",
            email=email,
            event_name=event_name,
            message=f"{organiser_name} asked to change {', '.join(fields)}. Reason: {reason}",
            event_id=event_id,
        )

    def cancellation_requested(
        self, *, email: str, event_id: uuid.UUID, event_name: str, organiser_name: str, reason: str
    ) -> None:
        self._delegate.cancellation_requested(
            email=email, event_id=event_id, event_name=event_name, organiser_name=organiser_name, reason=reason
        )
        self._record(
            "cancellation_requested",
            email=email,
            event_name=event_name,
            message=f"{organiser_name} asked to cancel the event. Reason: {reason}",
            event_id=event_id,
        )

    def cancellation_rejected(
        self, *, email: str, event_id: uuid.UUID, event_name: str, reason: str, rejection_reason: str
    ) -> None:
        self._delegate.cancellation_rejected(
            email=email, event_id=event_id, event_name=event_name, reason=reason, rejection_reason=rejection_reason
        )
        self._record(
            "cancellation_rejected",
            email=email,
            event_name=event_name,
            message=f"Your request to cancel the event was rejected, so it goes ahead. Reason: {rejection_reason}",
            event_id=event_id,
        )

    def event_cancelled(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        reason: str,
        recipient: CancellationRecipient,
    ) -> None:
        self._delegate.event_cancelled(
            email=email, event_id=event_id, event_name=event_name, reason=reason, recipient=recipient
        )
        self._record(
            "event_cancelled",
            email=email,
            event_name=event_name,
            message=f"The event was cancelled. Reason: {reason}",
            event_id=event_id,
        )

    def change_request_decided(
        self,
        *,
        email: str,
        event_id: uuid.UUID,
        event_name: str,
        decision: str,
        fields: list[str],
        rejection_reason: str | None,
        status_change: str | None,
        safety_review_required: bool,
        to_requester: bool,
    ) -> None:
        self._delegate.change_request_decided(
            email=email,
            event_id=event_id,
            event_name=event_name,
            decision=decision,
            fields=fields,
            rejection_reason=rejection_reason,
            status_change=status_change,
            safety_review_required=safety_review_required,
            to_requester=to_requester,
        )
        changed = ", ".join(fields)
        message = (
            f"Your request to change {changed} was {decision}."
            if to_requester
            else f"A change to {changed} was approved for your event."
        )
        if rejection_reason:
            message += f" Reason: {rejection_reason}"
        if status_change:
            message += f" The event goes back to {status_change}."
        if safety_review_required:
            message += " A new safety review is needed."
        self._record("change_request_decided", email=email, event_name=event_name, message=message, event_id=event_id)

    def arrangement_flagged(
        self, *, email: str, event_id: uuid.UUID, event_name: str, kind: str, label: str, fields: list[str]
    ) -> None:
        self._delegate.arrangement_flagged(
            email=email, event_id=event_id, event_name=event_name, kind=kind, label=label, fields=fields
        )
        self._record(
            "arrangement_flagged",
            email=email,
            event_name=event_name,
            message=f"A change to {', '.join(fields)} may affect the {kind} {label} arranged for this event. Please review it.",
            event_id=event_id,
        )

    def venue_held(
        self,
        *,
        email: str,
        booking_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        expires_at: datetime,
        stage: HoldStage,
    ) -> None:
        self._delegate.venue_held(
            email=email,
            booking_id=booking_id,
            event_name=event_name,
            venue_name=venue_name,
            starts_at=starts_at,
            ends_at=ends_at,
            expires_at=expires_at,
            stage=stage,
        )
        when = f"{_when(starts_at)} to {_when(ends_at)}"
        message = {
            "placed": f"{venue_name} is held for {when}. The hold expires {_when(expires_at)}.",
            "expiring": f"The hold on {venue_name} for {when} expires within 24 hours, at {_when(expires_at)}.",
            "expired": f"The hold on {venue_name} for {when} has expired.",
        }[stage]
        self._record("venue_held", email=email, event_name=event_name, message=message, booking_id=booking_id)

    def venue_unavailable(
        self,
        *,
        email: str,
        recipient: UnavailabilityRecipient,
        event_id: uuid.UUID,
        event_name: str,
        venue_name: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str,
        booking_references: list[str],
        next_action: str,
    ) -> None:
        self._delegate.venue_unavailable(
            email=email,
            recipient=recipient,
            event_id=event_id,
            event_name=event_name,
            venue_name=venue_name,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=reason,
            booking_references=booking_references,
            next_action=next_action,
        )
        self._record(
            "venue_unavailable",
            email=email,
            event_name=event_name,
            message=(
                f"{venue_name} is unavailable {_when(starts_at)} to {_when(ends_at)} ({reason}). "
                f"Affected: {', '.join(booking_references)}. Next: {next_action}"
            ),
            event_id=event_id,
        )


# The notifier the app uses: the logging stand-in, plus a row for each recipient (US31).
recording_notifier = RecordingNotifier(LoggingNotifier())

