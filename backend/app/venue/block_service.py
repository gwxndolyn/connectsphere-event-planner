"""US23a (SCRUM-90): Venue staff mark a venue unavailable for a period, and the bookings and holds it overlaps are
marked "Needs rearrangement" (D113), with each affected event's coordinator and organiser told (AC 4)."""

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import AuditAction, Event, EventAuditEntry, EventStatus
from app.notification.service import Notifier, UnavailabilityRecipient
from app.user.models import User
from app.venue.hold_service import expire_lapsed_holds
from app.venue.models import BLOCKING_STATUSES, Venue, VenueBlock, VenueBlockReason, VenueBooking
from app.venue.schemas import AffectedBookingOut, BookingEventOut, BookingVenueOut, VenueBlockOut, VenueBlockWrite

logger = logging.getLogger(__name__)

# US23b (SCRUM-91) AC 1: an affected event in these goes back to Planning until its venues are rearranged.
REOPENED_STATUSES = (EventStatus.CONFIRMED, EventStatus.PREPARATION)

REQUIRED_FIELDS = ("starts_at", "ends_at", "reason")
NOTE_MAX_LENGTH = 500
# DECISION-PENDING: D114 — AC 4's "next action", in each recipient's words. Finding the replacement is US23b's.
NEXT_ACTIONS: dict[UnavailabilityRecipient, str] = {
    "coordinator": "Find a replacement venue for the affected booking, or withdraw it.",
    "organiser": "Your event's coordinator will arrange a replacement venue. You don't need to do anything yet.",
}
# Matt's #133 review: the organiser of an event with no active coordinator isn't promised one is on it.
ORGANISER_WITHOUT_COORDINATOR = (
    "Your event has no active coordinator yet. A Coordinator Lead assigns one, who then arranges a replacement venue."
)
# AC 1: VenueBlockReason's values, compared as plain strings so the check doesn't rest on enum membership rules.
REASONS = frozenset(reason.value for reason in VenueBlockReason)


@dataclass
class _Notice:
    email: str
    recipient: UnavailabilityRecipient
    event_id: uuid.UUID
    event_name: str
    booking_references: list[str]
    next_action: str


def _validate(body: VenueBlockWrite, now: datetime) -> tuple[datetime, datetime, str, str | None]:
    """Every missing field at once, then every invalid one, so the form marks them together (AC 1, 2)."""
    values = body.model_dump()
    missing = [field for field in REQUIRED_FIELDS if values[field] is None or str(values[field]).strip() == ""]
    if missing:
        raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)
    starts_at, ends_at = body.starts_at, body.ends_at
    errors: dict[str, str] = {}
    for field, value in (("starts_at", starts_at), ("ends_at", ends_at)):
        if value.utcoffset() is None:
            errors[field] = "Give the time with a timezone offset, e.g. 2026-10-08T10:00:00+08:00."
    if not errors:
        # AC 2: a period can't end before it starts. Nor at its start: an empty period blocks nothing.
        if ends_at <= starts_at:
            errors["ends_at"] = "The end must be after the start."
        elif ends_at <= now:
            errors["ends_at"] = "This period has already ended."
    reason = str(body.reason).strip()
    if reason not in REASONS:
        allowed = ", ".join(member.value for member in VenueBlockReason)
        errors["reason"] = f"Unknown reason: {reason}. Allowed: {allowed}."
    note = body.note.strip() or None if body.note is not None else None
    if note is not None and len(note) > NOTE_MAX_LENGTH:
        errors["note"] = f"Keep the note to {NOTE_MAX_LENGTH} characters."
    if errors:
        ordered = {field: errors[field] for field in VenueBlockWrite.model_fields if field in errors}
        raise DomainError(422, "INVALID_BLOCK", fields=list(ordered), errors=ordered)
    return starts_at, ends_at, reason, note


def _notices(db: Session, affected: list[VenueBooking]) -> list[_Notice]:
    """AC 4: one notice per affected event for its assigned coordinator and one for its organiser, naming every
    booking of that event the period hit. Attendees aren't told. Read inside the transaction."""
    by_event: dict[uuid.UUID, list[VenueBooking]] = {}
    for booking in affected:
        by_event.setdefault(booking.event_id, []).append(booking)
    notices = []
    for event_id, bookings in by_event.items():
        event = db.get(Event, event_id)
        name = event.name or event.request_reference or str(event.id)
        references = [booking.reference for booking in sorted(bookings, key=lambda b: (b.starts_at, b.reference))]
        coordinator = db.get(User, event.coordinator_id) if event.coordinator_id is not None else None
        has_coordinator = coordinator is not None and coordinator.is_active
        for recipient, user_id in (("coordinator", event.coordinator_id), ("organiser", event.created_by_user_id)):
            user = db.get(User, user_id) if user_id is not None else None
            if user is None or not user.is_active:
                logger.warning("could not tell the %s of event %s its venue is unavailable: none active", recipient, event_id)
                continue
            next_action = (
                ORGANISER_WITHOUT_COORDINATOR if recipient == "organiser" and not has_coordinator else NEXT_ACTIONS[recipient]
            )
            notices.append(_Notice(user.email, recipient, event.id, name, references, next_action))
    return notices


def _back_to_planning(db: Session, event: Event, staff: User, now: datetime) -> None:
    """US23b (SCRUM-91) AC 1: a Confirmed or Preparation event whose venue became unavailable is back in Planning and
    no longer confirmed, as an approved significant change does (D105); History records both. Planning and Approved
    events stay as they are. The safety approval stands: the rearrangement may keep the same arrangements."""
    if event.status not in REOPENED_STATUSES:
        return
    previous = event.status.value
    confirmation = (
        {"confirmed_at": event.confirmed_at.isoformat(), "confirmed_by": str(event.confirmed_by_user_id)}
        if event.confirmed_at
        else None
    )
    for action, field, before, after in (
        (AuditAction.STATUS_CHANGED, "status", previous, EventStatus.PLANNING.value),
        (AuditAction.CONFIRMATION_CLEARED, "confirmation", confirmation, None),
    ):
        db.add(
            EventAuditEntry(
                event_id=event.id, user_id=staff.id, field_name=field, previous_value=before, new_value=after,
                action=action, created_at=now,
            )
        )
    event.status = EventStatus.PLANNING
    event.confirmed_at = None
    event.confirmed_by_user_id = None


def _affected_out(db: Session, bookings: list[VenueBooking]) -> list[AffectedBookingOut]:
    return [
        AffectedBookingOut(
            id=booking.id,
            reference=booking.reference,
            status=booking.status,
            event=BookingEventOut.model_validate(db.get(Event, booking.event_id)),
            starts_at=booking.starts_at,
            ends_at=booking.ends_at,
        )
        for booking in sorted(bookings, key=lambda booking: (booking.starts_at, booking.reference))
    ]


def _block_out(
    db: Session, block: VenueBlock, venue: Venue, affected: list[VenueBooking], already: Sequence[VenueBooking] = ()
) -> VenueBlockOut:
    return VenueBlockOut(
        id=block.id,
        venue=BookingVenueOut.model_validate(venue),
        starts_at=block.starts_at,
        ends_at=block.ends_at,
        reason=block.reason,
        note=block.note,
        created_by_user_id=block.created_by_user_id,
        created_at=block.created_at,
        affected_bookings=_affected_out(db, affected),
        already_affected_bookings=_affected_out(db, list(already)),
        ended_early_at=block.ended_early_at,
        scheduled_ends_at=block.scheduled_ends_at,
    )


class VenueBlockService:
    def create(
        self, db: Session, staff: User, venue_id: uuid.UUID, body: VenueBlockWrite, now: datetime, notifier: Notifier
    ) -> VenueBlockOut:
        """AC 1 to 4: record the period, mark every booking and hold it overlaps "Needs rearrangement" without
        changing its status (D113), then tell each affected event's coordinator and organiser. New requests and
        approvals in the period are refused by the availability check that already reads blocks (AC 5)."""
        starts_at, ends_at, reason, note = _validate(body, now)
        # A hold already past its expiry isn't affected: it lapses first (D109). The sweep commits on its own, so an
        # unknown venue below still sweeps; that's harmless, as every read sweeps the same way.
        expire_lapsed_holds(db, now, notifier)
        # AC 3: by the booking's occupied window, as the availability check compares a block with a request, so a
        # booking whose setup or turnaround falls in the period is affected too. Half-open: touching isn't
        # overlapping. Only bookings not yet over (Matt's #133 review): a period that began in the past doesn't
        # reach back to events that already took place.
        period = func.tstzrange(literal(starts_at), literal(ends_at), literal("[)"))
        occupied = func.tstzrange(VenueBooking.occupied_starts_at, VenueBooking.occupied_ends_at, literal("[)"))
        overlapping = (
            select(VenueBooking)
            .where(
                VenueBooking.venue_id == venue_id,
                VenueBooking.status.in_(BLOCKING_STATUSES),
                VenueBooking.occupied_ends_at > now,
                occupied.op("&&")(period),
            )
            .order_by(VenueBooking.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        # Lock order (Matt's #133 review): the bookings, then the venue, as Venue staff's approval takes them (the
        # booking, then the event, then the venue) and as a cancel does (TC-US9-24). The other order could deadlock
        # with an approval in flight. US23b (SCRUM-91): their events too, before the venue, for the same reason,
        # since an affected event may go back to Planning below.
        events = self._lock_events(db, list(db.scalars(overlapping)))
        # DECISION-PENDING: D22 — the venue FOR UPDATE, so a request in flight (which holds it FOR SHARE) either
        # commits first, and the second read below finds it, or waits and then sees the block.
        venue = db.scalars(select(Venue).where(Venue.id == venue_id).with_for_update()).one_or_none()
        if venue is None:
            raise DomainError(404, "NOT_FOUND")
        block = VenueBlock(
            venue_id=venue.id, starts_at=starts_at, ends_at=ends_at, reason=reason, note=note, created_by_user_id=staff.id
        )
        db.add(block)
        db.flush()
        found = list(db.scalars(overlapping))
        # D115: a booking an earlier period already marked keeps that one, and its people aren't told again; the
        # response lists it, so Venue staff see the period did reach it (Matt's #133 review).
        affected = [booking for booking in found if booking.rearrangement_block_id is None]
        already = [booking for booking in found if booking.rearrangement_block_id is not None]
        for booking in affected:
            booking.rearrangement_block_id = block.id
            booking.rearrangement_flagged_at = now
            booking.updated_at = now
        # US23b (SCRUM-91) AC 1: each affected event back to Planning. A request that committed while this waited
        # for the venue is the one booking whose event isn't locked yet; it's taken now.
        events |= self._lock_events(db, [booking for booking in affected if booking.event_id not in events])
        for event_id in sorted({booking.event_id for booking in affected}):
            _back_to_planning(db, events[event_id], staff, now)
        notices = _notices(db, affected)
        db.commit()
        db.refresh(block)

        result = _block_out(db, block, venue, affected, already)
        for notice in notices:
            # After the commit and best effort, as the other notices: a failure is logged and the block stands.
            try:
                notifier.venue_unavailable(
                    email=notice.email,
                    recipient=notice.recipient,
                    event_id=notice.event_id,
                    event_name=notice.event_name,
                    venue_name=venue.name,
                    starts_at=block.starts_at,
                    ends_at=block.ends_at,
                    reason=block.reason,
                    booking_references=notice.booking_references,
                    next_action=notice.next_action,
                )
            except Exception:
                logger.exception("could not tell the %s of event %s about block %s", notice.recipient, notice.event_id, block.id)
        return result


    def _lock_events(self, db: Session, bookings: list[VenueBooking]) -> dict[uuid.UUID, Event]:
        """The bookings' events FOR UPDATE, by id, as a booking request locks its event."""
        ids = sorted({booking.event_id for booking in bookings})
        if not ids:
            return {}
        locked = db.scalars(select(Event).where(Event.id.in_(ids)).order_by(Event.id).with_for_update())
        return {event.id: event for event in locked}

    def end_early(
        self, db: Session, staff: User, venue_id: uuid.UUID, block_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> VenueBlockOut:
        """US23b (SCRUM-91) AC 5 (D118): Venue staff end a period early, so the venue can be free again. Its end moves
        to now, or to its start if it hadn't begun (an empty period, overlapping nothing), keeping the end it had.
        A booking it marked still needs rearrangement until Venue staff confirm the coordinator's restore request.
        One that another period still overlaps now names that period instead (Matt's #131 review)."""
        marking = (
            select(VenueBooking)
            .where(
                VenueBooking.venue_id == venue_id,
                VenueBooking.rearrangement_block_id == block_id,
                VenueBooking.status.in_(BLOCKING_STATUSES),
            )
            .order_by(VenueBooking.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        # Lock order (Chloe's #135 review): the bookings it marks first, by id, then the venue, then the block, as
        # recording a block, an approval and confirming a restore all take bookings before the venue (#133's rule).
        db.scalars(marking).all()
        # D22: the venue FOR UPDATE, as recording a block locks it.
        venue = db.scalars(select(Venue).where(Venue.id == venue_id).with_for_update()).one_or_none()
        block = db.scalars(
            select(VenueBlock).where(VenueBlock.id == block_id).with_for_update()
        ).one_or_none() if venue is not None else None
        if block is None or block.venue_id != venue.id:
            raise DomainError(404, "NOT_FOUND")
        if block.ends_at <= now:
            raise DomainError(409, "BLOCK_ENDED", message="This period has already ended.")
        block.scheduled_ends_at = block.ends_at
        block.ends_at = max(now, block.starts_at)
        block.ended_early_at = now
        block.ended_early_by_user_id = staff.id
        db.flush()

        # Read again under the venue lock: another period ending early may have moved a booking to this one's marker
        # while this waited. It committed first, so taking that booking now waits on nobody.
        marked = list(db.scalars(marking))
        still_marked = []
        for booking in marked:
            occupied = func.tstzrange(literal(booking.occupied_starts_at), literal(booking.occupied_ends_at), literal("[)"))
            other = db.scalars(
                select(VenueBlock)
                .where(
                    VenueBlock.venue_id == venue.id,
                    VenueBlock.id != block.id,
                    func.tstzrange(VenueBlock.starts_at, VenueBlock.ends_at, literal("[)")).op("&&")(occupied),
                )
                .order_by(VenueBlock.starts_at, VenueBlock.id)
                .limit(1)
            ).one_or_none()
            if other is not None:
                booking.rearrangement_block_id = other.id
                booking.updated_at = now
            else:
                still_marked.append(booking)
        notices = [
            (coordinator.email, booking, db.get(Event, booking.event_id))
            for booking in sorted(still_marked, key=lambda booking: (booking.starts_at, booking.reference))
            for coordinator in [self._coordinator(db, booking)]
            if coordinator is not None
        ]
        db.commit()
        db.refresh(block)
        # The bookings this period alone kept from their venue: their coordinators may now ask to restore them, so
        # each is told (Matt's #134 review). After the commit and best effort.
        for email, booking, event in notices:
            try:
                notifier.venue_period_ended(
                    email=email,
                    booking_id=booking.id,
                    booking_reference=booking.reference,
                    event_name=event.name or event.request_reference or str(event.id),
                    venue_name=venue.name,
                    ended_at=now,
                )
            except Exception:
                logger.exception("could not tell the coordinator of booking %s its venue is free again", booking.id)
        return _block_out(db, block, venue, still_marked)

    def _coordinator(self, db: Session, booking: VenueBooking) -> User | None:
        event = db.get(Event, booking.event_id)
        user = db.get(User, event.coordinator_id) if event.coordinator_id is not None else None
        if user is None or not user.is_active:
            logger.warning("no active coordinator to tell that booking %s's venue is free again", booking.id)
            return None
        return user


block_service = VenueBlockService()
