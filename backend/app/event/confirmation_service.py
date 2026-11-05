import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.equipment.models import (
    EquipmentLineStatus,
    EquipmentRequestLine,
    EquipmentReservation,
    TechStaffAssignment,
)
from app.event.assignment_service import MISSING_NAME, MISSING_REFERENCE
from app.event.final_fields import fill_final_fields
from app.event.models import DeliveryMode, Event, EventStatus
from app.event.request_schemas import EventRequestOut, ReadinessItemOut, ReadinessOut
from app.event.review_flag_service import event_flags, is_open
from app.notification.service import Notifier
from app.safety.models import CHANGE_AREAS
from app.safety.state import latest_review, safety_state
from app.user.models import User
from app.venue.availability import review_reason, venue_change
from app.venue.models import LIVE_BOOKING_STATUSES, Venue, VenueBooking, VenueBookingStatus

logger = logging.getLogger(__name__)

# US18 AC 5: only an event still being arranged can be confirmed. Cancelled, Rejected and an
# already Confirmed event are refused, and so is anything not yet approved. DECISION-PENDING: D86 —
# Approved counts as well as Planning: approving moves a request to Planning (D53), but events approved
# before that (and the seeded ones) are still Approved.
CONFIRMABLE_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING)
# The statuses an event's coordinator works it in, so the readiness list shows in each (widens D11).
WORKING_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING, EventStatus.CONFIRMED, EventStatus.PREPARATION)


class ConfirmationService:
    """SCRUM-85 (US18): the assigned coordinator confirms an event once its arrangements are ready, then
    moves it on to Preparation."""

    def readiness(self, db: Session, request_id: uuid.UUID, coordinator: User, now: datetime) -> ReadinessOut:
        event = self._assigned(db, request_id, coordinator, lock=False)
        if event.status not in WORKING_STATUSES:
            raise DomainError(409, "CONFIRMATION_NOT_ALLOWED", status=event.status.value)
        return self._readiness(db, event, now, lock=False)[0]

    def confirm(
        self, db: Session, request_id: uuid.UUID, coordinator: User, now: datetime, notifier: Notifier
    ) -> EventRequestOut:
        event = self._assigned(db, request_id, coordinator, lock=True)
        if event.status not in CONFIRMABLE_STATUSES:
            raise DomainError(409, "CONFIRMATION_NOT_ALLOWED", status=event.status.value)
        # AC 1, 5: no override. The bookings and lines are locked with the event, so a Venue staff
        # decision can't land between this check and the status change.
        readiness, approved = self._readiness(db, event, now, lock=True)
        if not readiness.ready:
            raise DomainError(
                409,
                "EVENT_NOT_READY",
                outstanding=[item.model_dump() for item in readiness.items if not item.complete],
                items=[item.model_dump() for item in readiness.items],
            )

        # An online event has no booking to take its dates from: it already has them.
        starts_at = min((booking.starts_at for booking, _ in approved), default=event.start_at)
        ends_at = max((booking.ends_at for booking, _ in approved), default=event.end_at)
        # The primary venue first, as attendees see it (US24 D70), then the others by when they start.
        venues = list(
            dict.fromkeys(venue.name for booking, venue in sorted(approved, key=lambda pair: not pair[0].is_primary))
        )
        # An event approved into Planning already holds its date (D123) and keeps it; an older Approved one
        # takes its bookings' span.
        fill_final_fields(
            event,
            starts_at=starts_at,
            ends_at=ends_at,
            capacity=event.expected_attendees or max((b.expected_attendees for b, _ in approved), default=0),
        )
        self._open_registration(event, now)
        event.status = EventStatus.CONFIRMED
        event.confirmed_at = now
        event.confirmed_by_user_id = coordinator.id
        db.flush()
        db.refresh(event, ["coordinator", "decided_by"])
        result = EventRequestOut.model_validate(event)
        # The event's own times, so the notice and the event page agree (TC-US17-24).
        notice = (event.created_by_user_id, event.request_reference, event.name, event.start_at, event.end_at, venues)
        db.commit()

        self._notify(db, notifier, event.id, *notice)
        return result

    def start_preparation(self, db: Session, request_id: uuid.UUID, coordinator: User) -> EventRequestOut:
        """AC 6: a Confirmed event moves to Preparation, which is when Venue staff and Technical support
        preparation updates open. Those updates don't exist yet, so nothing else changes here."""
        event = self._assigned(db, request_id, coordinator, lock=True)
        if event.status != EventStatus.CONFIRMED:
            raise DomainError(409, "PREPARATION_NOT_ALLOWED", status=event.status.value)
        # US30a: an event without an approved safety review doesn't move to Preparation, however it
        # came to be Confirmed.
        if event.safety_approved_at is None:
            raise DomainError(409, "SAFETY_NOT_APPROVED")
        event.status = EventStatus.PREPARATION
        db.flush()
        db.refresh(event, ["coordinator", "decided_by"])
        result = EventRequestOut.model_validate(event)
        db.commit()
        return result

    def complete(self, db: Session, request_id: uuid.UUID, coordinator: User, now: datetime) -> EventRequestOut:
        """Core feature "Event Status Management": an event in Preparation is marked Completed by its
        coordinator once it has ended. Completed is terminal: nothing reopens it."""
        event = self._assigned(db, request_id, coordinator, lock=True)
        if event.status != EventStatus.PREPARATION:
            raise DomainError(409, "COMPLETION_NOT_ALLOWED", status=event.status.value)
        # DECISION-PENDING: D120 — only after the event's end, so a running event can't be closed early.
        if event.end_at is None or event.end_at > now:
            raise DomainError(409, "EVENT_NOT_ENDED", ends_at=event.end_at.isoformat() if event.end_at else None)
        event.status = EventStatus.COMPLETED
        db.flush()
        db.refresh(event, ["coordinator", "decided_by"])
        result = EventRequestOut.model_validate(event)
        db.commit()
        return result

    @staticmethod
    def _open_registration(event: Event, now: datetime) -> None:
        """Core feature "Attendee Registration": a request that asked for attendee registration
        (`registration_required`, US1) opens for registration when it is confirmed, so an event made in the
        app reaches the attendee board. DECISION-PENDING: D121 — the window opens on confirmation and closes
        when the event starts; a window or flag the event already holds is kept."""
        if not event.registration_required or event.registration_enabled:
            return
        event.registration_enabled = True
        event.registration_opens_at = event.registration_opens_at or now
        event.registration_closes_at = event.registration_closes_at or event.start_at

    def _assigned(self, db: Session, request_id: uuid.UUID, coordinator: User, *, lock: bool) -> Event:
        query = select(Event).where(Event.id == request_id)
        event = db.scalars(query.with_for_update() if lock else query).one_or_none()
        # D48: only the event's assigned coordinator. Anyone else's, an unassigned event, a draft or an
        # unknown id is 404, never 403, as for other people's records (§1a).
        if event is None or event.status == EventStatus.DRAFT or event.coordinator_id != coordinator.id:
            raise DomainError(404, "NOT_FOUND")
        return event

    def _readiness(
        self, db: Session, event: Event, now: datetime, *, lock: bool
    ) -> tuple[ReadinessOut, list[tuple[VenueBooking, Venue]]]:
        """AC 1, 2: the venues arranged (US24's rule, D72), the equipment approved and reserved, technical
        support assigned and the safety check approved. Also returns the approved bookings, which
        confirming turns into the event's date, time and venues."""
        bookings_query = (
            select(VenueBooking, Venue)
            .join(Venue, Venue.id == VenueBooking.venue_id)
            .where(VenueBooking.event_id == event.id, VenueBooking.status.in_(LIVE_BOOKING_STATUSES))
            .order_by(VenueBooking.starts_at, VenueBooking.reference)
        )
        if lock:
            bookings_query = bookings_query.with_for_update(of=VenueBooking)
        bookings = [(booking, venue) for booking, venue in db.execute(bookings_query).all()]

        items = self._venue_items(event, bookings, now)
        equipment_item, approved_lines = self._equipment_item(db, event, lock)
        items.append(equipment_item)
        items.append(self._technical_support_item(db, approved_lines))
        safety_done = event.safety_approved_at is not None
        items.append(
            ReadinessItemOut(
                kind="safety",
                name="Safety check",
                complete=safety_done,
                detail="Approved by the Safety Officer." if safety_done else self._safety_wait(db, event),
            )
        )
        # US29b (SCRUM-142) D104: once a significant change has flagged its arrangements, each must be reviewed.
        flagged = event_flags(db, event.id)
        if flagged:
            still_open = [flag for flag in flagged if is_open(db, flag)]
            items.append(
                ReadinessItemOut(
                    kind="review_flags",
                    name="Review after change",
                    complete=not still_open,
                    detail=(
                        f"{len(still_open)} arrangement{'s' if len(still_open) != 1 else ''} to review after an approved change."
                        if still_open
                        else "Every flagged arrangement is reviewed."
                    ),
                )
            )
        approved_bookings = [(b, v) for b, v in bookings if b.status == VenueBookingStatus.APPROVED]
        return ReadinessOut(ready=all(item.complete for item in items), items=items), approved_bookings

    def _venue_items(
        self, event: Event, bookings: list[tuple[VenueBooking, Venue]], now: datetime
    ) -> list[ReadinessItemOut]:
        """One item per live booking, then what US24's `venues_arranged` (D72) also asks of the set: one
        primary, and allocations that hold the expected attendance (D67). Rejected and withdrawn bookings
        aren't required. An online event needs no venue."""
        if event.delivery_mode == DeliveryMode.ONLINE:
            return [
                ReadinessItemOut(kind="venue", name="Venue", complete=True, detail="This is an online event, so no venue is needed.")
            ]
        if not bookings:
            return [ReadinessItemOut(kind="venue", name="Venue", complete=False, detail="No venue has been requested yet.")]
        items = []
        for booking, venue in bookings:
            approved = booking.status == VenueBookingStatus.APPROVED
            # US23a (SCRUM-90, D113): a live booking a venue unavailability period overlaps keeps its status, so it
            # is outstanding here until it is rearranged, approved or not, as venues_arranged also says.
            flagged = booking.rearrangement_block_id is not None
            # US20 AC 2 (SCRUM-147, D119): so is one whose venue's capacity or hours no longer fit it, by the rule the
            # booking's `venue_changed` and venues_arranged read.
            change = venue_change(venue, booking, now)
            if flagged:
                detail = f"Booking {booking.reference} needs rearrangement: the venue has become unavailable."
            elif change is not None:
                detail = f"Booking {booking.reference} needs review: {review_reason(booking, change)}."
            elif approved:
                detail = f"Booking {booking.reference} is approved."
            else:
                detail = f"Booking {booking.reference} is waiting for Venue staff to approve it."
            items.append(
                ReadinessItemOut(
                    kind="venue",
                    name=f"{venue.name}, {booking.purpose}",
                    complete=approved and not flagged and change is None,
                    detail=detail,
                )
            )
        primaries = sum(booking.is_primary for booking, _ in bookings)
        if primaries != 1:
            items.append(
                ReadinessItemOut(
                    kind="venue",
                    name="Primary venue",
                    complete=False,
                    detail="Choose which venue attendees see as the primary one."
                    if primaries == 0
                    else "More than one venue is marked primary.",
                )
            )
        allocated = sum(booking.expected_attendees for booking, _ in bookings)
        if event.expected_attendees is not None and allocated < event.expected_attendees:
            items.append(
                ReadinessItemOut(
                    kind="venue",
                    name="Attendance allocated",
                    complete=False,
                    detail=f"The venues hold {allocated} of the {event.expected_attendees} expected attendees.",
                )
            )
        return items

    def _equipment_item(
        self, db: Session, event: Event, lock: bool
    ) -> tuple[ReadinessItemOut, list[EquipmentRequestLine]]:
        """Any requested equipment reserved (AC 1): every line that isn't rejected approved by Tech support
        (US26) and reserved (US27). Also returns the approved lines, which technical support follows."""
        query = select(EquipmentRequestLine).where(
            EquipmentRequestLine.event_id == event.id, EquipmentRequestLine.status != EquipmentLineStatus.REJECTED
        )
        lines = list(db.scalars(query.with_for_update() if lock else query).all())
        if not lines:
            return (
                ReadinessItemOut(kind="equipment", name="Equipment", complete=True, detail="No equipment was requested."),
                [],
            )
        approved = [line for line in lines if line.status == EquipmentLineStatus.APPROVED]
        reserved = set(
            db.scalars(
                select(EquipmentReservation.request_line_id).where(
                    EquipmentReservation.request_line_id.in_([line.id for line in approved])
                )
            )
        )
        pending = len(lines) - len(approved)
        unreserved = sum(1 for line in approved if line.id not in reserved)
        noun = "line" if len(lines) == 1 else "lines"
        if pending:
            detail = f"{pending} of {len(lines)} equipment {noun} {'is' if pending == 1 else 'are'} waiting for Tech support to approve."
        elif unreserved:
            detail = f"{unreserved} of {len(lines)} approved equipment {noun} {'is' if unreserved == 1 else 'are'} not reserved yet."
        else:
            return (
                ReadinessItemOut(kind="equipment", name="Equipment", complete=True, detail="Every equipment line is approved and reserved."),
                approved,
            )
        return ReadinessItemOut(kind="equipment", name="Equipment", complete=False, detail=detail), approved

    def _technical_support_item(self, db: Session, approved_lines: list[EquipmentRequestLine]) -> ReadinessItemOut:
        """Technical support arranged (AC 1): once the event has an approved technical support request, at
        least one Tech support staff member is assigned (US14, D80). Without one nobody is needed."""
        if not approved_lines:
            return ReadinessItemOut(
                kind="technical_support",
                name="Technical support",
                complete=True,
                detail="No technical support was requested.",
            )
        assigned = db.scalar(
            select(func.count())
            .select_from(TechStaffAssignment)
            .where(
                TechStaffAssignment.event_id == approved_lines[0].event_id,
                TechStaffAssignment.unassigned_at.is_(None),
            )
        )
        if assigned:
            return ReadinessItemOut(
                kind="technical_support",
                name="Technical support",
                complete=True,
                detail=f"{assigned} Tech support staff {'member is' if assigned == 1 else 'members are'} assigned.",
            )
        return ReadinessItemOut(
            kind="technical_support",
            name="Technical support",
            complete=False,
            detail="No Tech support staff member is assigned yet.",
        )

    def _safety_wait(self, db: Session, event: Event) -> str:
        """What the coordinator still has to do about the safety check (US30a AC 4): after a rejection,
        read the comments, revise the arrangement and send it back."""
        latest = latest_review(db, event.id)
        state = safety_state(event, latest)
        if state == "rejected" and latest is not None:
            return (
                f"Rejected by the Safety Officer: {latest.comments} "
                "Revise the arrangement, then send it for another review."
            )
        if state == "changes_requested" and latest is not None:
            # US30b AC 2: the areas are marked for review; nothing else is reset, the coordinator decides.
            areas = ", ".join(label for key, label in CHANGE_AREAS if key in (latest.areas or []))
            return (
                f"The Safety Officer asked for changes to {areas}: {latest.comments} "
                "Make the changes, then mark them done."
            )
        if latest is not None:
            return "Sent for another safety review."
        return "Waiting for the Safety Officer's approval."

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
