import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, literal, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event, EventStatus
from app.notification.service import BookingDecision, Notifier
from app.user.models import User, UserRole
from app.venue.models import ROOM_LAYOUTS, LIVE_BOOKING_STATUSES, Venue, VenueBlock, VenueBooking, VenueBookingStatus
from app.venue.schemas import (
    BookingEventOut,
    BookingRejectWrite,
    BookingVenueOut,
    BookingWarning,
    VenueBookingCreatedOut,
    VenueBookingOut,
    VenueBookingWrite,
)
from app.venue.service import VENUE_STAFF_ROLES, _clean_tags, _slot

logger = logging.getLogger(__name__)

# US22 AC 1: only an Approved event or one in Planning can have a venue requested.
BOOKABLE_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING)
REQUIRED_FIELDS = ("event_id", "venue_id", "starts_at", "ends_at", "expected_attendees", "room_layout")
# A booking's tag field → the D18 list it draws from (TAG_FIELDS in app/venue/service.py).
TAG_VOCABULARIES = {
    "required_facilities": "facilities",
    "required_accessibility_features": "accessibility_features",
}
NO_OVERLAP = "venue_bookings_no_overlap"
# Two inserts for overlapping windows at the same moment can each wait on the other's row in the
# exclusion index; Postgres aborts one with deadlock_detected. That request runs once more, and then
# sees or waits for the winner and is refused with VENUE_UNAVAILABLE (AC 7).
DEADLOCK_DETECTED = "40P01"
CREATE_ATTEMPTS = 2
# Backstop for anything the checks below miss: each named CHECK in PR 1's migration maps to its field.
CONSTRAINT_FIELDS = {
    "venue_bookings_window_valid": "ends_at",
    "venue_bookings_expected_attendees_positive": "expected_attendees",
    "venue_bookings_room_layout_known": "room_layout",
    "venue_bookings_required_facilities_known": "required_facilities",
    "venue_bookings_required_accessibility_features_known": "required_accessibility_features",
}


def may_book(event: Event, coordinator: User) -> bool:
    """Whether this coordinator may request venues for, and see the bookings of, this event: only the
    coordinator assigned to it (US22 AC 1). An unassigned event has nobody who may."""
    # DECISION-PENDING: D20 — since US10a (SCRUM-13), events.coordinator_id. Withdrawing still
    # belongs to whoever made the request (withdraw), even if the event is later reassigned.
    return coordinator.role == UserRole.COORDINATOR and event.coordinator_id == coordinator.id


def _find_conflict(db: Session, venue_id: uuid.UUID, starts_at: datetime, ends_at: datetime) -> VenueBooking | None:
    """A live booking at the venue whose [starts_at, ends_at) overlaps this window: the same rule
    as the exclusion constraint, asked first so the refusal can name the window (D21, D22)."""
    return db.scalars(
        select(VenueBooking)
        .where(
            VenueBooking.venue_id == venue_id,
            VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
            VenueBooking.starts_at < ends_at,
            VenueBooking.ends_at > starts_at,
        )
        .order_by(VenueBooking.starts_at)
        .limit(1)
    ).first()


def _find_block(db: Session, venue_id: uuid.UUID, starts_at: datetime, ends_at: datetime) -> VenueBlock | None:
    """A venue block (US2's unavailability period, AC 3) overlapping this window by the same [)
    rule, so back-to-back is fine. Written as && on the range venue_blocks_venue_window indexes."""
    window = func.tstzrange(literal(starts_at), literal(ends_at), literal("[)"))
    return db.scalars(
        select(VenueBlock)
        .where(VenueBlock.venue_id == venue_id, _slot(VenueBlock).op("&&")(window))
        .order_by(VenueBlock.starts_at)
        .limit(1)
    ).first()


def _find_buffered_conflict(db: Session, booking: VenueBooking, venue: Venue) -> VenueBooking | VenueBlock | None:
    """US4 AC 3: what stops this request being approved. Its window, widened by the venue's setup
    before and turnaround after, may not overlap an approved booking's widened window or a block at
    the venue. Both bookings are at one venue, so they share its buffers: two windows clash when one
    starts less than setup + turnaround after the other ends. A booking is reported before a block.

    Only approved bookings count for the buffers: a pending one can't overlap this window at all
    (venue_bookings_no_overlap), and if a pending neighbour inside the buffers counted too, two
    requests close together would each block the other until one was rejected (PR #73 review)."""
    # DECISION-PENDING: D38 — buffers from the venue as it is now, checked only on approval: create
    # still checks the plain window (D22), so a request can be made and then fail approval on buffers.
    # US13 (SCRUM-16) moves the buffers into create and stores each booking's occupied window; once it
    # lands, compare those here and drop this function.
    setup = timedelta(minutes=venue.setup_minutes)
    turnaround = timedelta(minutes=venue.turnaround_minutes)
    gap = setup + turnaround
    other = db.scalars(
        select(VenueBooking)
        .where(
            VenueBooking.venue_id == venue.id,
            VenueBooking.id != booking.id,
            VenueBooking.status == VenueBookingStatus.APPROVED,
            VenueBooking.starts_at < booking.ends_at + gap,
            VenueBooking.ends_at > booking.starts_at - gap,
        )
        .order_by(VenueBooking.starts_at)
        .limit(1)
    ).first()
    if other is not None:
        return other
    return _find_block(db, venue.id, booking.starts_at - setup, booking.ends_at + turnaround)


def _overlaps(conflict: VenueBooking | VenueBlock, booking: VenueBooking) -> bool:
    return conflict.starts_at < booking.ends_at and conflict.ends_at > booking.starts_at


def _unavailable(conflict: VenueBooking | VenueBlock | None, *, buffers: bool = False) -> DomainError:
    """`buffers`: the clash is only with the venue's setup and turnaround, not the window itself
    (US4 approval), so the message says too close rather than already booked (PR #73 review)."""
    if conflict is None:
        return DomainError(409, "VENUE_UNAVAILABLE", message="This venue is already booked for that time.")
    window = {"starts_at": conflict.starts_at.isoformat(), "ends_at": conflict.ends_at.isoformat()}
    what = "a venue closure" if isinstance(conflict, VenueBlock) else "a booking"
    if buffers:
        return DomainError(
            409,
            "VENUE_UNAVAILABLE",
            conflict=window,
            buffers=True,
            message=(
                f"Too close to {what} from {window['starts_at']} to {window['ends_at']} "
                "to fit the venue's setup and turnaround."
            ),
        )
    reason = "unavailable" if isinstance(conflict, VenueBlock) else "already booked"
    return DomainError(
        409,
        "VENUE_UNAVAILABLE",
        conflict=window,
        message=f"This venue is {reason} from {window['starts_at']} to {window['ends_at']}.",
    )


def _words(tag: str) -> str:
    return tag.replace("_", " ")


def _validate(values: dict[str, object], now: datetime) -> dict[str, object]:
    """Checks a request's own values, collecting every invalid field so the form can mark them all
    at once. Returns the values with tags cleaned and blank requirements as null."""
    errors: dict[str, str] = {}
    cleaned = dict(values)
    starts_at, ends_at = values["starts_at"], values["ends_at"]
    for field, value in (("starts_at", starts_at), ("ends_at", ends_at)):
        if value.utcoffset() is None:
            errors[field] = "Give the time with a timezone offset, e.g. 2026-10-08T10:00:00+08:00."
    if not errors:
        if ends_at <= starts_at:
            errors["ends_at"] = "End time must be after the start time."
        if starts_at < now:
            errors["starts_at"] = "Start time can't be in the past."
    if values["expected_attendees"] < 1:
        errors["expected_attendees"] = "Expected attendance must be at least 1."
    cleaned["room_layout"] = str(values["room_layout"]).strip()
    if cleaned["room_layout"] not in ROOM_LAYOUTS:
        errors["room_layout"] = f"Unknown room layout: {cleaned['room_layout']}. Allowed: {', '.join(ROOM_LAYOUTS)}."
    for field, vocabulary in TAG_VOCABULARIES.items():
        cleaned[field] = _clean_tags(field, values[field] or [], errors, vocabulary)
    requirements = values["special_requirements"]
    cleaned["special_requirements"] = requirements.strip() or None if requirements is not None else None
    if errors:
        # Fields in the body's order, so a form marks them top to bottom.
        ordered = {field: errors[field] for field in VenueBookingWrite.model_fields if field in errors}
        raise DomainError(422, "INVALID_BOOKING", fields=list(ordered), errors=ordered)
    return cleaned


def _warnings(booking: VenueBooking, venue: Venue) -> list[BookingWarning]:
    """What the request needs that the venue lacks (AC 3). The request still saves."""
    warnings = [
        BookingWarning(field=field, item=tag, message=f"This venue doesn't list {_words(tag)} among its {label}.")
        for field, have, label in (
            ("required_facilities", venue.facilities, "facilities"),
            ("required_accessibility_features", venue.accessibility_features, "accessibility features"),
        )
        for tag in getattr(booking, field)
        if tag not in have
    ]
    if booking.room_layout not in venue.room_layouts:
        warnings.append(
            BookingWarning(
                field="room_layout",
                item=booking.room_layout,
                message=f"This venue doesn't offer the {_words(booking.room_layout)} layout.",
            )
        )
    return warnings


def _out(booking: VenueBooking, event: Event, venue: Venue) -> VenueBookingOut:
    return VenueBookingOut(
        id=booking.id,
        event=BookingEventOut.model_validate(event),
        venue=BookingVenueOut.model_validate(venue),
        requested_by_user_id=booking.requested_by_user_id,
        starts_at=booking.starts_at,
        ends_at=booking.ends_at,
        expected_attendees=booking.expected_attendees,
        room_layout=booking.room_layout,
        required_facilities=booking.required_facilities,
        required_accessibility_features=booking.required_accessibility_features,
        special_requirements=booking.special_requirements,
        status=booking.status,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        withdrawn_at=booking.withdrawn_at,
        decided_at=booking.decided_at,
        decided_by_user_id=booking.decided_by_user_id,
        rejection_reason=booking.rejection_reason,
        alternative_suggestion=booking.alternative_suggestion,
    )


class VenueBookingService:
    """A coordinator's venue booking requests (US22, SCRUM-89) and Venue Staff's decision on them
    (US4, SCRUM-8)."""

    def create(
        self, db: Session, coordinator: User, body: VenueBookingWrite, now: datetime, notifier: Notifier
    ) -> VenueBookingCreatedOut:
        for _ in range(CREATE_ATTEMPTS):
            try:
                booking, event, venue = self._insert(db, coordinator, body, now)
                break
            except OperationalError as error:
                if getattr(error.orig, "sqlstate", None) != DEADLOCK_DETECTED:
                    raise
                db.rollback()
                logger.info("venue booking request deadlocked with another; trying once more")
        else:
            raise _unavailable(None)

        result = VenueBookingCreatedOut(
            **_out(booking, event, venue).model_dump(), warnings=_warnings(booking, venue)
        )
        self._notify_staff(db, notifier, booking, event, venue)
        return result

    def _insert(
        self, db: Session, coordinator: User, body: VenueBookingWrite, now: datetime
    ) -> tuple[VenueBooking, Event, Venue]:
        """Checks and saves one request, committed. Raises the refusals in the order of §3."""
        values = body.model_dump()
        missing = [field for field in REQUIRED_FIELDS if values[field] is None]
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)
        cleaned = _validate(values, now)

        # FOR SHARE: a concurrent status change or venue edit waits for this request, and two
        # requests don't block each other. The overlap race is the exclusion constraint's job.
        event = db.scalars(select(Event).where(Event.id == cleaned["event_id"]).with_for_update(read=True)).one_or_none()
        # A draft is owner-only (D11): refusing it with 409 would reveal that it exists.
        if event is None or event.status == EventStatus.DRAFT or not may_book(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        if event.status not in BOOKABLE_STATUSES:
            raise DomainError(409, "EVENT_NOT_BOOKABLE", status=event.status.value)
        venue = db.scalars(select(Venue).where(Venue.id == cleaned["venue_id"]).with_for_update(read=True)).one_or_none()
        if venue is None or not venue.is_active:
            raise DomainError(404, "NOT_FOUND")
        if cleaned["expected_attendees"] > venue.capacity:
            raise DomainError(
                422,
                "VENUE_CAPACITY_EXCEEDED",
                fields=["expected_attendees"],
                capacity=venue.capacity,
                message=f"Expected attendance is more than this venue's capacity of {venue.capacity}.",
            )
        conflict = _find_conflict(db, venue.id, cleaned["starts_at"], cleaned["ends_at"])
        if conflict is not None:
            raise _unavailable(conflict)
        # DECISION-PENDING: D22 — blocks are checked here only, not by a constraint: a block added
        # while this request is in flight isn't seen. US23a's block screens should lock the venue
        # row FOR UPDATE, which this request's FOR SHARE then waits on.
        block = _find_block(db, venue.id, cleaned["starts_at"], cleaned["ends_at"])
        if block is not None:
            raise _unavailable(block)

        booking = VenueBooking(requested_by_user_id=coordinator.id, **cleaned)
        db.add(booking)
        self._commit(db, venue.id, cleaned["starts_at"], cleaned["ends_at"])
        db.refresh(booking)
        return booking, event, venue

    def withdraw(self, db: Session, coordinator: User, booking_id: uuid.UUID, now: datetime) -> VenueBookingOut:
        """AC 5: a pending request can be withdrawn by the coordinator who made it, which frees the
        window. Anyone else's booking is 404, never 403."""
        booking = db.scalars(
            select(VenueBooking).where(VenueBooking.id == booking_id).with_for_update()
        ).one_or_none()
        if booking is None or booking.requested_by_user_id != coordinator.id:
            raise DomainError(404, "NOT_FOUND")
        if booking.status != VenueBookingStatus.REQUESTED:
            raise DomainError(409, "BOOKING_NOT_PENDING", status=booking.status.value)
        booking.status = VenueBookingStatus.WITHDRAWN
        booking.withdrawn_at = now
        booking.updated_at = now
        db.commit()
        db.refresh(booking)
        return _out(booking, db.get(Event, booking.event_id), db.get(Venue, booking.venue_id))

    def approve(
        self, db: Session, staff: User, booking_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> VenueBookingOut:
        """US4 AC 2, 3, 7: approves the request as a whole, which reserves the venue for the event.
        Refused, with no override, while the venue is booked or blocked for any part of the window
        with its buffers, once the start has passed, or above the venue's capacity; the request then
        stays pending, to be rejected or withdrawn."""
        booking = self._lock_pending(db, booking_id)
        # Pending requests don't expire yet (US25), so one can still be waiting after its start;
        # approving it would reserve a window that's gone. Create refuses a past start too.
        if booking.starts_at <= now:
            raise DomainError(
                409, "BOOKING_EXPIRED", message="This request's start time has passed. It can only be rejected."
            )
        # The event FOR SHARE, as create reads it. The venue FOR UPDATE: the exclusion constraint
        # doesn't cover buffers, so two approvals at one venue take turns, and a new request there
        # (which reads the venue FOR SHARE) waits for the decision.
        event = db.scalars(select(Event).where(Event.id == booking.event_id).with_for_update(read=True)).one()
        venue = db.scalars(select(Venue).where(Venue.id == booking.venue_id).with_for_update()).one()
        if event.status not in BOOKABLE_STATUSES:
            raise DomainError(409, "EVENT_NOT_BOOKABLE", status=event.status.value)
        # DECISION-PENDING: D39 — a deactivated venue can't be reserved; it reads as unavailable.
        if not venue.is_active:
            raise DomainError(409, "VENUE_UNAVAILABLE", message="This venue is inactive, so it can't be reserved.")
        # Capacity can be edited after the request (US20), so it's checked again, as create does.
        if booking.expected_attendees > venue.capacity:
            raise DomainError(
                409,
                "VENUE_CAPACITY_EXCEEDED",
                capacity=venue.capacity,
                message=f"Expected attendance is now more than this venue's capacity of {venue.capacity}.",
            )
        # DECISION-PENDING: D22 — blocks are checked here only, not by a constraint (see _insert).
        conflict = _find_buffered_conflict(db, booking, venue)
        if conflict is not None:
            raise _unavailable(conflict, buffers=not _overlaps(conflict, booking))
        return self._decide(db, notifier, staff, booking, event, venue, VenueBookingStatus.APPROVED, now)

    def reject(
        self,
        db: Session,
        staff: User,
        booking_id: uuid.UUID,
        body: BookingRejectWrite,
        now: datetime,
        notifier: Notifier,
    ) -> VenueBookingOut:
        """US4 AC 4, 5, 8: rejects the request as a whole, optionally saying why and what else might
        work. The window is freed, and the event keeps its status (Approved or Planning), so its
        coordinator can request another venue."""
        reason = body.reason.strip() or None if body.reason is not None else None
        alternative = body.alternative_suggestion.strip() or None if body.alternative_suggestion is not None else None
        booking = self._lock_pending(db, booking_id)
        event = db.get(Event, booking.event_id)
        venue = db.get(Venue, booking.venue_id)
        # Set with the status in one flush: the notes alone on a pending booking break
        # venue_bookings_rejection_notes_only_when_rejected, and loading anything could autoflush them.
        booking.rejection_reason = reason
        booking.alternative_suggestion = alternative
        return self._decide(db, notifier, staff, booking, event, venue, VenueBookingStatus.REJECTED, now)

    def _lock_pending(self, db: Session, booking_id: uuid.UUID) -> VenueBooking:
        """The booking, locked FOR UPDATE so a decision and a withdrawal can't both land."""
        booking = db.scalars(
            select(VenueBooking).where(VenueBooking.id == booking_id).with_for_update()
        ).one_or_none()
        if booking is None:
            raise DomainError(404, "NOT_FOUND")
        if booking.status != VenueBookingStatus.REQUESTED:
            raise DomainError(409, "BOOKING_NOT_PENDING", status=booking.status.value)
        return booking

    def _decide(
        self,
        db: Session,
        notifier: Notifier,
        staff: User,
        booking: VenueBooking,
        event: Event,
        venue: Venue,
        status: VenueBookingStatus,
        now: datetime,
    ) -> VenueBookingOut:
        booking.status = status
        booking.decided_at = now
        booking.decided_by_user_id = staff.id
        booking.updated_at = now
        db.commit()
        db.refresh(booking)
        result = _out(booking, event, venue)
        self._notify_coordinators(db, notifier, booking, event, venue, status.value)
        return result

    def _notify_coordinators(
        self, db: Session, notifier: Notifier, booking: VenueBooking, event: Event, venue: Venue, decision: BookingDecision
    ) -> None:
        """US4 AC 6: the coordinator who made the request hears the decision, and so does the event's
        assigned coordinator if that's someone else now. Runs after the commit; a failure is logged
        and the decision stands."""
        # DECISION-PENDING: D40 — the requester and the assigned coordinator, once each, if active.
        try:
            ids = {booking.requested_by_user_id, event.coordinator_id} - {None}
            recipients = db.scalars(
                select(User).where(User.id.in_(ids), User.is_active.is_(True)).order_by(User.email)
            ).all()
            if not recipients:
                logger.warning("no active coordinator to notify about venue booking %s", booking.id)
                return
            for user in recipients:
                notifier.venue_booking_decided(
                    email=user.email,
                    booking_id=booking.id,
                    decision=decision,
                    event_name=event.name or event.request_reference or str(event.id),
                    venue_name=venue.name,
                    starts_at=booking.starts_at,
                    ends_at=booking.ends_at,
                    reason=booking.rejection_reason,
                    alternative_suggestion=booking.alternative_suggestion,
                )
        except Exception:
            logger.exception("could not notify coordinators about venue booking %s", booking.id)

    def pending(self, db: Session) -> list[VenueBookingOut]:
        """Venue Staff's review queue (AC 4): Requested bookings, oldest first."""
        rows = db.execute(
            select(VenueBooking, Event, Venue)
            .join(Event, Event.id == VenueBooking.event_id)
            .join(Venue, Venue.id == VenueBooking.venue_id)
            .where(VenueBooking.status == VenueBookingStatus.REQUESTED)
            .order_by(VenueBooking.created_at, VenueBooking.id)
        )
        return [_out(booking, event, venue) for booking, event, venue in rows]

    def for_event(self, db: Session, reader: User, event_id: uuid.UUID) -> list[VenueBookingOut]:
        """An event's bookings in every status, soonest first. Venue Staff see any event's;
        a coordinator only one they may book (D20). A draft is 404 to both (D11)."""
        event = db.get(Event, event_id)
        if event is None or event.status == EventStatus.DRAFT:
            raise DomainError(404, "NOT_FOUND")
        if reader.role not in VENUE_STAFF_ROLES and not may_book(event, reader):
            raise DomainError(404, "NOT_FOUND")
        rows = db.execute(
            select(VenueBooking, Venue)
            .join(Venue, Venue.id == VenueBooking.venue_id)
            .where(VenueBooking.event_id == event_id)
            .order_by(VenueBooking.starts_at, VenueBooking.created_at, VenueBooking.id)
        )
        return [_out(booking, event, venue) for booking, venue in rows]

    def _commit(self, db: Session, venue_id: uuid.UUID, starts_at: datetime, ends_at: datetime) -> None:
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint == NO_OVERLAP:
                # AC 7: another request for an overlapping window committed first. It's visible now.
                raise _unavailable(_find_conflict(db, venue_id, starts_at, ends_at)) from None
            field = CONSTRAINT_FIELDS.get(constraint)
            if field is None:
                raise
            message = f"Invalid value for {_words(field)}."
            raise DomainError(422, "INVALID_BOOKING", fields=[field], errors={field: message}) from None

    def _notify_staff(
        self, db: Session, notifier: Notifier, booking: VenueBooking, event: Event, venue: Venue
    ) -> None:
        """AC 6: every active Venue Staff member hears of the new request once. Runs after the
        commit; a failure is logged and the booking stands."""
        try:
            staff = db.scalars(
                select(User)
                .where(User.role.in_(VENUE_STAFF_ROLES), User.is_active.is_(True))
                .order_by(User.email)
            ).all()
            if not staff:
                logger.warning("no active Venue Staff to notify about venue booking %s", booking.id)
                return
            event_name = event.name or event.request_reference or str(event.id)
            for member in staff:
                notifier.venue_booking_requested(
                    email=member.email,
                    booking_id=booking.id,
                    event_name=event_name,
                    venue_name=venue.name,
                    starts_at=booking.starts_at,
                    ends_at=booking.ends_at,
                )
        except Exception:
            logger.exception("could not notify Venue Staff about venue booking %s", booking.id)


booking_service = VenueBookingService()
