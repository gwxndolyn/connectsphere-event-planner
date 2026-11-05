import logging
import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import DeliveryMode, Event, EventStatus
from app.event.self_decision import refuse_self_decision
from app.notification.service import BookingDecision, Notifier, RestoreDecision
from app.registration.models import ACTIVE_STATUSES, Registration
from app.user.models import User, UserRole
from app.venue.availability import (
    Conflict,
    Evaluation,
    HoursBreach,
    Window,
    block_conflicts,
    evaluate_booking,
    evaluate_window,
    VenueChange,
    venue_change,
)
from app.venue.hold_service import HOLD_MAX_LENGTH, HOLD_WARNING, expire_lapsed_holds, notice_for, send
from app.venue.models import (
    BLOCKING_STATUSES,
    LIVE_BOOKING_STATUSES,
    ROOM_LAYOUTS,
    PreparationStatus,
    Venue,
    VenueBooking,
    VenueBookingStatus,
    clear_restore_request,
)
from app.venue.schemas import (
    BlockSummaryOut,
    HoldEventOut,
    RestoreDeclineWrite,
    VenueHoldWrite,
    BookingConflictOut,
    BookingEvaluationOut,
    BookingEventOut,
    BookingHoursOut,
    BookingPreparationWrite,
    BookingRejectWrite,
    BookingUnavailabilityOut,
    BookingVenueOut,
    BookingWarning,
    EventVenueBookingsOut,
    VenueBookingCreatedOut,
    VenueBookingOut,
    VenueBookingWrite,
    WindowOut,
)
from app.venue.service import VENUE_STAFF_ROLES, _clean_tags

logger = logging.getLogger(__name__)

# US22 AC 1: only an Approved event or one in Planning can have a venue requested.
BOOKABLE_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING)
# US24 (SCRUM-128): a purpose too, for each of an event's venues (D66).
REQUIRED_FIELDS = ("event_id", "venue_id", "starts_at", "ends_at", "expected_attendees", "room_layout", "purpose")
PURPOSE_MAX_LENGTH = 100
# US24 (D71): the Organiser reads an event's venues once its request is approved, not before.
ORGANISER_VISIBLE_STATUSES = (
    EventStatus.APPROVED,
    EventStatus.PLANNING,
    EventStatus.CONFIRMED,
    EventStatus.CANCELLED,
    EventStatus.COMPLETED,
)
# A booking's tag field → the D18 list it draws from (TAG_FIELDS in app/venue/service.py).
TAG_VOCABULARIES = {
    "required_facilities": "facilities",
    "required_accessibility_features": "accessibility_features",
}
NO_OVERLAP = "venue_bookings_no_overlap"
# US23b (SCRUM-91, D117): a second live replacement for the same booking, caught by the index.
ONE_LIVE_REPLACEMENT = "venue_bookings_one_live_replacement"
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
    "venue_bookings_purpose_valid": "purpose",
}


def may_book(event: Event, coordinator: User) -> bool:
    """Whether this coordinator may request venues for, and see the bookings of, this event: only the
    coordinator assigned to it (US22 AC 1). An unassigned event has nobody who may."""
    # DECISION-PENDING: D20 — since US10a (SCRUM-13), events.coordinator_id. Withdrawing still
    # belongs to whoever made the request (withdraw), even if the event is later reassigned.
    return coordinator.holds(UserRole.COORDINATOR) and event.coordinator_id == coordinator.id


VENUE_TIMEZONE = ZoneInfo("Asia/Singapore")


def _local(instant: datetime) -> str:
    return instant.astimezone(VENUE_TIMEZONE).strftime("%d %b %H:%M")


def _unavailable(conflict: Conflict | None, occupied: Window | None = None) -> DomainError:
    """409 VENUE_UNAVAILABLE (deviation 27). `conflict` keeps US22's starts_at/ends_at, the clashing
    booking's or block's own window, and adds US13 AC 4's `kind`, `occupied` and exact `overlap`."""
    if conflict is None:
        return DomainError(409, "VENUE_UNAVAILABLE", message="This venue is already booked for that time.")
    # DECISION-PENDING: D35 — a coordinator sees the overlap and the kind, never the other booking's
    # reference; Venue Staff get that from the evaluation (AC 4).
    body: dict[str, object] = {
        "conflict": {
            "kind": conflict.kind,
            **conflict.window.as_json(),
            "occupied": conflict.occupied.as_json(),
            "overlap": conflict.overlap.as_json(),
        }
    }
    if occupied is not None:
        body["occupied"] = occupied.as_json()
    reason = "unavailable" if conflict.kind == "block" else "already booked"
    message = (
        f"This venue is {reason} from {conflict.window.starts_at.isoformat()} to {conflict.window.ends_at.isoformat()}. "
        f"With setup and turnaround, that overlaps this request from {_local(conflict.overlap.starts_at)} "
        f"to {_local(conflict.overlap.ends_at)}."
    )
    return DomainError(409, "VENUE_UNAVAILABLE", message=message, **body)


def _overlaps(window: Window, booking: VenueBooking) -> bool:
    """Whether the clash is with the booking's own window, not only its setup and turnaround."""
    return window.starts_at < booking.ends_at and window.ends_at > booking.starts_at


def _approval_unavailable(conflict: Conflict, booking: VenueBooking) -> DomainError:
    """US4's approval refusal, 409 VENUE_UNAVAILABLE, as #73 built it: `conflict` is the clashing
    booking's or block's own window, and `buffers` is true when the clash is only with the venue's
    setup and turnaround, so the message says too close rather than already booked (PR #73 review)."""
    window = conflict.window.as_json()
    if not _overlaps(conflict.window, booking):
        what = "a venue closure" if conflict.kind == "block" else "a booking"
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
    reason = "unavailable" if conflict.kind == "block" else "already booked"
    return DomainError(
        409,
        "VENUE_UNAVAILABLE",
        conflict=window,
        message=f"This venue is {reason} from {window['starts_at']} to {window['ends_at']}.",
    )


def _outside_hours(breach: HoursBreach, occupied: Window, status_code: int = 422) -> DomainError:
    """VENUE_OUTSIDE_HOURS (US13 AC 5, D32): `fields` names the end that breaches. 422 for a request
    (its fields); 409 at approval, which has no body: like US4's capacity re-check, it's the booking's
    state now that refuses it (deviation 43)."""
    return DomainError(
        status_code,
        "VENUE_OUTSIDE_HOURS",
        fields=breach.fields,
        opens_at=breach.opens_at.isoformat(),
        closes_at=breach.closes_at.isoformat(),
        occupied=occupied.as_json(),
        message=(
            f"With setup and turnaround the venue would be occupied from {_local(occupied.starts_at)} to "
            f"{_local(occupied.ends_at)}, outside its opening hours of {breach.opens_at:%H:%M} to {breach.closes_at:%H:%M}."
        ),
    )


def _first_booking_conflict(evaluation: Evaluation) -> Conflict | None:
    return next((conflict for conflict in evaluation.conflicts if conflict.kind == "booking"), None)


def _window_out(window: Window) -> WindowOut:
    return WindowOut(starts_at=window.starts_at, ends_at=window.ends_at)


def _evaluation_out(booking: VenueBooking, evaluation: Evaluation) -> BookingEvaluationOut:
    breach = evaluation.outside_hours
    return BookingEvaluationOut(
        booking_id=booking.id,
        reference=booking.reference,
        occupied=_window_out(evaluation.occupied),
        conflicts=[
            BookingConflictOut(
                kind=conflict.kind,
                reference=conflict.reference,
                note=conflict.note,
                starts_at=conflict.window.starts_at,
                ends_at=conflict.window.ends_at,
                occupied=_window_out(conflict.occupied),
                overlap=_window_out(conflict.overlap),
            )
            for conflict in evaluation.conflicts
        ],
        outside_hours=(
            BookingHoursOut(opens_at=breach.opens_at, closes_at=breach.closes_at, fields=breach.fields) if breach else None
        ),
        clear=evaluation.clear,
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
    # DECISION-PENDING: D66 — US24 AC 1: what the venue is for, 1 to 100 characters once trimmed.
    cleaned["purpose"] = str(values["purpose"]).strip()
    if not cleaned["purpose"]:
        errors["purpose"] = "Say what this venue is for, e.g. Main hall or Breakout A."
    elif len(cleaned["purpose"]) > PURPOSE_MAX_LENGTH:
        errors["purpose"] = f"Keep the purpose to {PURPOSE_MAX_LENGTH} characters."
    if errors:
        # Fields in the body's order, so a form marks them top to bottom.
        ordered = {field: errors[field] for field in VenueBookingWrite.model_fields if field in errors}
        raise DomainError(422, "INVALID_BOOKING", fields=list(ordered), errors=ordered)
    return cleaned


def _schedule_errors(event: Event, starts_at: datetime, ends_at: datetime) -> dict[str, str]:
    """US24 AC 1: a booking's own window falls within the event's schedule; setup and turnaround may
    run outside it. Nothing to check for an event with no schedule yet."""
    # DECISION-PENDING: D65 — start_at to end_at once set (approving sets them, D123); before that, as on an
    # event approved before SCRUM-84 was reopened, a preferred day between the preferred times (Singapore time).
    errors: dict[str, str] = {}
    if event.start_at is not None and event.end_at is not None:
        span = f"{_local(event.start_at)} to {_local(event.end_at)}"
        if starts_at < event.start_at:
            errors["starts_at"] = f"Starts before the event's schedule ({span})."
        if ends_at > event.end_at:
            errors["ends_at"] = f"Ends after the event's schedule ({span})."
        return errors
    if not (event.preferred_dates and event.preferred_start_time and event.preferred_end_time):
        return errors
    local_start = starts_at.astimezone(VENUE_TIMEZONE)
    if local_start.date() not in event.preferred_dates:
        days = ", ".join(day.strftime("%d %b") for day in sorted(event.preferred_dates))
        return {"starts_at": f"Not on a day in the event's schedule ({days})."}
    opens = datetime.combine(local_start.date(), event.preferred_start_time, VENUE_TIMEZONE)
    closes = datetime.combine(local_start.date(), event.preferred_end_time, VENUE_TIMEZONE)
    hours = f"{event.preferred_start_time:%H:%M} to {event.preferred_end_time:%H:%M}"
    if starts_at < opens:
        errors["starts_at"] = f"Starts before the event's schedule ({hours})."
    if ends_at > closes:
        errors["ends_at"] = f"Ends after the event's schedule ({hours})."
    return errors


def _hold_expiry(value: datetime | None, starts_at: datetime | None, now: datetime) -> datetime:
    """US25 AC 1: a hold's expiry is required and in the future; D108: at most 14 days ahead. It must also come
    before the held time starts, since a hold on a slot that has begun keeps nothing for anyone."""
    if value is None:
        raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=["hold_expires_at"])
    if value.utcoffset() is None:
        message = "Give the expiry with a timezone offset, e.g. 2026-10-08T17:00:00+08:00."
    elif value <= now:
        message = "The hold must expire in the future."
    elif value > now + HOLD_MAX_LENGTH:
        message = f"A hold can last at most {HOLD_MAX_LENGTH.days} days."
    elif starts_at is not None and starts_at.utcoffset() is not None and value > starts_at:
        message = "The hold must expire before the held time starts."
    else:
        return value
    raise DomainError(422, "INVALID_HOLD", fields=["hold_expires_at"], errors={"hold_expires_at": message})


def _needs_rearrangement(booking: VenueBooking) -> bool:
    """US23a (SCRUM-90) AC 3: a venue unavailability period overlaps this live booking or hold (D113)."""
    return booking.rearrangement_block_id is not None and booking.status in BLOCKING_STATUSES


def _unavailability(booking: VenueBooking, venue: Venue, now: datetime) -> BookingUnavailabilityOut | None:
    """US24 AC 4 (D71): why this venue needs replacing, if it does."""
    if booking.status == VenueBookingStatus.REJECTED:
        return BookingUnavailabilityOut(
            kind="rejected", reason=booking.rejection_reason, alternative_suggestion=booking.alternative_suggestion
        )
    if _needs_rearrangement(booking):
        return BookingUnavailabilityOut(
            kind="venue_unavailable",
            block=BlockSummaryOut.model_validate(booking.rearrangement_block),
            flagged_at=booking.rearrangement_flagged_at,
        )
    if booking.status in LIVE_BOOKING_STATUSES and not venue.is_active:
        return BookingUnavailabilityOut(kind="venue_inactive")
    # US20 AC 2 (SCRUM-147, D119): Venue staff changed the capacity or hours and it no longer fits ("Needs review").
    change = venue_change(venue, booking, now)
    if change is not None:
        return BookingUnavailabilityOut(
            kind="venue_changed",
            detail="capacity" if change.capacity is not None else "hours",
            capacity=change.capacity,
            opens_at=change.hours.opens_at if change.hours else None,
            closes_at=change.hours.closes_at if change.hours else None,
        )
    return None


def _hold_change_message(booking: VenueBooking, change: VenueChange) -> str:
    """US20 AC 2 (Calvin's #138 review): why a hold its venue's change no longer fits can't be confirmed."""
    reasons = []
    if change.capacity is not None:
        reasons.append(f"capacity is now {change.capacity}, below this hold's {booking.expected_attendees}")
    if change.hours is not None:
        opens, closes = change.hours.opens_at.strftime("%H:%M"), change.hours.closes_at.strftime("%H:%M")
        reasons.append(f"hours are now {opens}–{closes}, and this hold's setup or turnaround falls outside them")
    return f"This venue's {' and its '.join(reasons)}, so it can't be confirmed."


def _next_action(
    booking: VenueBooking, venue: Venue, now: datetime
) -> Literal["venue_staff_to_decide", "coordinator_to_rebook", "coordinator_to_confirm", "venue_staff_to_restore", "none"]:
    """US24 AC 4 (D71): who acts next on this booking. US25: a hold waits for the coordinator (AC 5). US23a: one the
    venue's unavailability overlaps, hold or not, is the coordinator's to rearrange (AC 4)."""
    # US23b (SCRUM-91) AC 5: the coordinator asked to restore it; Venue staff confirm or decline (D118).
    if _needs_rearrangement(booking) and booking.restore_requested_at is not None:
        return "venue_staff_to_restore"
    if _needs_rearrangement(booking):
        return "coordinator_to_rebook"
    if booking.status == VenueBookingStatus.HELD:
        return "coordinator_to_confirm"
    # DECISION-PENDING: D71 — an inactive venue can't be approved (D39) or used, so it's rebooked. US20 AC 2 (D119): so
    # is one whose capacity or hours no longer fit.
    if _unavailability(booking, venue, now) is not None:
        return "coordinator_to_rebook"
    if booking.status == VenueBookingStatus.REQUESTED:
        return "venue_staff_to_decide"
    return "none"


def _arranged(event: Event, live: list[tuple[VenueBooking, Venue]], now: datetime) -> bool:
    """US24 AC 7: every required venue approved. `live` pairs each live booking with its venue."""
    # DECISION-PENDING: D72 — an online event needs none; otherwise every live booking is Approved,
    # exactly one is primary, and (D67, CS3-24) together they hold the expected attendance.
    if event.delivery_mode == DeliveryMode.ONLINE:
        return True
    if not live or any(booking.status != VenueBookingStatus.APPROVED for booking, _ in live):
        return False
    # US23a (SCRUM-90): an approved venue that has since become unavailable is not arranged (D113).
    if any(_needs_rearrangement(booking) for booking, _ in live):
        return False
    # US20 AC 2 (SCRUM-147, D119): nor one whose venue's capacity or hours no longer fit it, by the rule the booking's
    # `venue_changed` reads.
    if any(venue_change(venue, booking, now) is not None for booking, venue in live):
        return False
    if sum(booking.is_primary for booking, _ in live) != 1:
        return False
    return event.expected_attendees is None or sum(b.expected_attendees for b, _ in live) >= event.expected_attendees


def venues_arranged(db: Session, event: Event, now: datetime) -> bool:
    """US24 AC 7, for US18 (SCRUM-85) to confirm an event by: whether its venues are arranged (D72). Each live booking
    with its venue, in one query."""
    live = db.execute(
        select(VenueBooking, Venue)
        .join(Venue, Venue.id == VenueBooking.venue_id)
        .where(VenueBooking.event_id == event.id, VenueBooking.status.in_(LIVE_BOOKING_STATUSES))
    ).all()
    return _arranged(event, [(booking, venue) for booking, venue in live], now)


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


def _out(
    booking: VenueBooking, event: Event, venue: Venue, now: datetime, replacement_id: uuid.UUID | None = None
) -> VenueBookingOut:
    return VenueBookingOut(
        id=booking.id,
        event=BookingEventOut.model_validate(event),
        venue=BookingVenueOut.model_validate(venue),
        requested_by_user_id=booking.requested_by_user_id,
        reference=booking.reference,
        starts_at=booking.starts_at,
        ends_at=booking.ends_at,
        occupied_starts_at=booking.occupied_starts_at,
        occupied_ends_at=booking.occupied_ends_at,
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
        purpose=booking.purpose,
        is_primary=booking.is_primary,
        preparation_status=booking.preparation_status,
        unavailability=_unavailability(booking, venue, now),
        next_action=_next_action(booking, venue, now),
        hold_expires_at=booking.hold_expires_at,
        held_by_user_id=booking.held_by_user_id,
        expired_at=booking.expired_at,
        replaces_booking_id=booking.replaces_booking_id,
        replacement_booking_id=replacement_id,
        replaced_at=booking.replaced_at,
        restore_requested_at=booking.restore_requested_at,
        restore_requested_by_user_id=booking.restore_requested_by_user_id,
        restore_declined_at=booking.restore_declined_at,
        restore_decline_reason=booking.restore_decline_reason,
    )


def _replacements(db: Session, originals: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    """US23b (SCRUM-91, D117): each booking's requested or approved replacement, by the booking it replaces."""
    if not originals:
        return {}
    rows = db.execute(
        select(VenueBooking.replaces_booking_id, VenueBooking.id).where(
            VenueBooking.replaces_booking_id.in_(originals),
            VenueBooking.status.in_((VenueBookingStatus.REQUESTED, VenueBookingStatus.APPROVED)),
        )
    ).all()
    return {original: replacement for original, replacement in rows}


def _replaceable(db: Session, event: Event, original_id: uuid.UUID, holding: bool) -> VenueBooking:
    """US23b (SCRUM-91) AC 3 (D117): the booking a new request replaces, locked: one of this event's that needs
    rearrangement, with no live replacement yet. Venue staff's holds don't replace bookings."""
    if holding:
        raise DomainError(
            422,
            "INVALID_BOOKING",
            fields=["replaces_booking_id"],
            errors={"replaces_booking_id": "Only the event's coordinator can request a replacement venue."},
        )
    original = db.scalars(
        select(VenueBooking).where(VenueBooking.id == original_id).with_for_update()
    ).one_or_none()
    if original is None or original.event_id != event.id:
        raise DomainError(
            422,
            "INVALID_BOOKING",
            fields=["replaces_booking_id"],
            errors={"replaces_booking_id": "Choose one of this event's bookings that needs rearrangement."},
        )
    if not _needs_rearrangement(original):
        raise DomainError(
            409,
            "BOOKING_NOT_REPLACEABLE",
            status=original.status.value,
            message="Only a booking that needs rearrangement can be replaced.",
        )
    existing = _replacements(db, [original.id]).get(original.id)
    if existing is not None:
        reference = db.get(VenueBooking, existing).reference
        raise DomainError(
            409,
            "REPLACEMENT_EXISTS",
            reference=reference,
            message=f"Booking {reference} is already the replacement. Withdraw it before requesting another.",
        )
    return original


class VenueBookingService:
    """A coordinator's venue booking requests (US22, SCRUM-89) and Venue Staff's decision on them
    (US4, SCRUM-8)."""

    def create(
        self, db: Session, coordinator: User, body: VenueBookingWrite, now: datetime, notifier: Notifier
    ) -> VenueBookingCreatedOut:
        # US25: a lapsed hold frees its window before this request is checked against it (D109).
        expire_lapsed_holds(db, now, notifier)
        booking, event, venue = self._insert_with_retry(db, coordinator, body, now)
        result = VenueBookingCreatedOut(
            **_out(booking, event, venue, now).model_dump(), warnings=_warnings(booking, venue)
        )
        self._notify_staff(db, notifier, booking, event, venue)
        return result

    def place_hold(
        self, db: Session, staff: User, body: VenueHoldWrite, now: datetime, notifier: Notifier
    ) -> VenueBookingCreatedOut:
        """US25 (SCRUM-93) AC 1, 2: Venue staff hold a venue for an event and time until an expiry. Checked as a
        request is (the event's schedule, capacity, opening hours, and live bookings, holds and blocks), and kept
        out of the window by the same guard. The event's coordinator is told, and warned at once if it expires
        within 24 hours (AC 4)."""
        values = body.model_dump()
        # Every missing field at once, the expiry with the request's own (as create names every gap).
        missing = [field for field in (*REQUIRED_FIELDS, "hold_expires_at") if values[field] is None]
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)
        expiry = _hold_expiry(body.hold_expires_at, body.starts_at, now)
        expire_lapsed_holds(db, now, notifier)
        booking_body = VenueBookingWrite(**body.model_dump(exclude={"hold_expires_at"}))
        booking, event, venue = self._insert_with_retry(db, staff, booking_body, now, hold_expires_at=expiry)
        result = VenueBookingCreatedOut(
            **_out(booking, event, venue, now).model_dump(), warnings=_warnings(booking, venue)
        )
        send(notifier, notice_for(db, booking, "placed"))
        # DECISION-PENDING: D109 — a hold placed with less than 24 hours left warns at once (AC 4). _insert marked
        # it warned in the same commit as the hold, so a sweep in between can't warn it a second time.
        if booking.hold_warned_at is not None:
            send(notifier, notice_for(db, booking, "expiring"))
        return result

    def _insert_with_retry(
        self, db: Session, user: User, body: VenueBookingWrite, now: datetime, hold_expires_at: datetime | None = None
    ) -> tuple[VenueBooking, Event, Venue]:
        for _ in range(CREATE_ATTEMPTS):
            try:
                return self._insert(db, user, body, now, hold_expires_at)
            except OperationalError as error:
                if getattr(error.orig, "sqlstate", None) != DEADLOCK_DETECTED:
                    raise
                db.rollback()
                logger.info("venue booking request deadlocked with another; trying once more")
        raise _unavailable(None)

    def _insert(
        self, db: Session, user: User, body: VenueBookingWrite, now: datetime, hold_expires_at: datetime | None = None
    ) -> tuple[VenueBooking, Event, Venue]:
        """Checks and saves one request, or (US25) a hold when `hold_expires_at` is given, committed. Raises the
        refusals in the order of §3."""
        values = body.model_dump()
        missing = [field for field in REQUIRED_FIELDS if values[field] is None]
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)
        cleaned = _validate(values, now)

        # FOR UPDATE (US24): two requests for the same event wait for each other, so only one can become
        # its first, primary booking (D68); requests for other events don't. A status change waits too.
        # The overlap race is the exclusion constraint's job.
        event = db.scalars(select(Event).where(Event.id == cleaned["event_id"]).with_for_update()).one_or_none()
        # A draft is owner-only (D11): refusing it with 409 would reveal that it exists. A request is the event's
        # coordinator's; a hold is any Venue staff member's (US25 AC 1), so their router decides who may.
        holding = hold_expires_at is not None
        if event is None or event.status == EventStatus.DRAFT or not (holding or may_book(event, user)):
            raise DomainError(404, "NOT_FOUND")
        if event.status not in BOOKABLE_STATUSES:
            raise DomainError(409, "EVENT_NOT_BOOKABLE", status=event.status.value)
        # US25: only the event's coordinator confirms or declines a hold (D20), so one on an unassigned event would block
        # the venue with nobody to act on it until it lapsed. hold_events leaves such events out too (D112).
        if holding and event.coordinator_id is None:
            raise DomainError(409, "EVENT_NOT_BOOKABLE", status=event.status.value, reason="no_coordinator")
        if cleaned.get("replaces_booking_id") is not None:
            _replaceable(db, event, cleaned["replaces_booking_id"], holding)
        schedule_errors = _schedule_errors(event, cleaned["starts_at"], cleaned["ends_at"])
        if schedule_errors:
            raise DomainError(422, "INVALID_BOOKING", fields=list(schedule_errors), errors=schedule_errors)
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
        # US13: the window the venue's own buffers make this request occupy (AC 1, 2), checked
        # against its hours first (AC 5, D32), then live bookings and blocks (AC 3). The same rule US4
        # calls before approving.
        # DECISION-PENDING: D22 — blocks are checked here only, not by a constraint: a block added
        # while this request is in flight isn't seen. US23a's block screens should lock the venue
        # row FOR UPDATE, which this request's FOR SHARE then waits on.
        evaluation = evaluate_window(db, venue, cleaned["starts_at"], cleaned["ends_at"])
        if evaluation.outside_hours is not None:
            raise _outside_hours(evaluation.outside_hours, evaluation.occupied)
        if evaluation.conflicts:
            raise _unavailable(evaluation.conflicts[0], evaluation.occupied)

        # DECISION-PENDING: D68 — the event's first live booking is its primary venue.
        has_primary = db.scalar(
            select(
                exists().where(
                    VenueBooking.event_id == event.id,
                    VenueBooking.is_primary.is_(True),
                    VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
                )
            )
        )
        booking = VenueBooking(
            requested_by_user_id=user.id,
            occupied_starts_at=evaluation.occupied.starts_at,
            occupied_ends_at=evaluation.occupied.ends_at,
            # DECISION-PENDING: D111 — a hold isn't one of the event's venues, so never its primary (AC 6).
            is_primary=not has_primary and not holding,
            **cleaned,
        )
        if holding:
            # US25 AC 1: the hold must lapse before the venue's setup for it begins, or it keeps nothing.
            if hold_expires_at > evaluation.occupied.starts_at:
                raise DomainError(
                    422,
                    "INVALID_HOLD",
                    fields=["hold_expires_at"],
                    errors={"hold_expires_at": "The hold must expire before the venue's setup for it starts."},
                )
            booking.status = VenueBookingStatus.HELD
            booking.held_by_user_id = user.id
            booking.hold_expires_at = hold_expires_at
            if hold_expires_at - HOLD_WARNING <= now:
                booking.hold_warned_at = now
        db.add(booking)
        self._commit(db, venue, cleaned["starts_at"], cleaned["ends_at"])
        db.refresh(booking)
        return booking, event, venue

    def withdraw(
        self, db: Session, coordinator: User, booking_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> VenueBookingOut:
        """AC 5: a pending request can be withdrawn by the coordinator now assigned to its event, which
        frees the window. After a reassignment (SCRUM-83) that is the new coordinator, not whoever
        made the request. Anyone else's booking is 404, never 403. Since US24 (SCRUM-128) an approved
        booking can be withdrawn too, to change or cancel one of an event's venues; Venue staff hear of
        it, and it keeps who approved it (D77). The event's other bookings are untouched."""
        # US25: a hold past its expiry lapses first, so it's Expired rather than declined (D109).
        expire_lapsed_holds(db, now, notifier)
        booking = db.scalars(
            select(VenueBooking).where(VenueBooking.id == booking_id).with_for_update()
        ).one_or_none()
        event = db.get(Event, booking.event_id) if booking is not None else None
        if booking is None or event is None or not may_book(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        # DECISION-PENDING: D69 — withdraw, then request again, is how one venue is changed or cancelled.
        # Approved bookings can be withdrawn too, so the refusal says the booking isn't live (#100 review).
        # DECISION-PENDING: D110 — US25: declining a hold is withdrawing it (AC 7).
        if booking.status not in BLOCKING_STATUSES:
            raise DomainError(409, "BOOKING_NOT_LIVE", status=booking.status.value)
        was_approved = booking.status == VenueBookingStatus.APPROVED
        clear_restore_request(booking)
        booking.status = VenueBookingStatus.WITHDRAWN
        booking.withdrawn_at = now
        booking.updated_at = now
        db.commit()
        db.refresh(booking)
        venue = db.get(Venue, booking.venue_id)
        result = _out(booking, event, venue, now)
        if was_approved:
            self._notify_staff_withdrawn(db, notifier, booking, event, venue)
        return result

    def confirm_hold(
        self, db: Session, coordinator: User, booking_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> VenueBookingOut:
        """US25 AC 5: the event's coordinator confirms a held venue, which becomes a request Venue staff then
        approve, before the hold's expiry. Anyone else's booking is 404, as for withdraw."""
        expire_lapsed_holds(db, now, notifier)
        found = db.get(VenueBooking, booking_id)
        if found is None:
            raise DomainError(404, "NOT_FOUND")
        # The event FOR UPDATE, as create locks it, so this and another request can't both make a primary (D68).
        event = db.scalars(select(Event).where(Event.id == found.event_id).with_for_update()).one()
        if not may_book(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        booking = db.scalars(
            select(VenueBooking)
            .where(VenueBooking.id == booking_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        if booking.status != VenueBookingStatus.HELD:
            raise DomainError(409, "HOLD_NOT_HELD", status=booking.status.value)
        # US23a (SCRUM-90): Venue staff couldn't approve it in the unavailable period (AC 5), so it can't be confirmed.
        if _needs_rearrangement(booking):
            raise DomainError(
                409,
                "VENUE_UNAVAILABLE",
                message="This venue has become unavailable for part of the held time, so the hold can't be confirmed.",
            )
        # US20 AC 2 (SCRUM-147, D119; Calvin's #138 review): nor if the venue's capacity or hours no longer fit it,
        # which Venue staff couldn't approve either (US4).
        change = venue_change(db.get(Venue, booking.venue_id), booking, now)
        if change is not None:
            raise DomainError(409, "VENUE_UNAVAILABLE", message=_hold_change_message(booking, change))
        if event.status not in BOOKABLE_STATUSES:
            raise DomainError(409, "EVENT_NOT_BOOKABLE", status=event.status.value)
        has_primary = db.scalar(
            select(
                exists().where(
                    VenueBooking.event_id == event.id,
                    VenueBooking.is_primary.is_(True),
                    VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
                )
            )
        )
        # DECISION-PENDING: D111 — the coordinator becomes the requester, so Venue staff may approve it (D51); it
        # keeps who held it and the expiry, which Venue staff must approve it by.
        booking.status = VenueBookingStatus.REQUESTED
        booking.requested_by_user_id = coordinator.id
        booking.is_primary = not has_primary
        booking.updated_at = now
        db.commit()
        db.refresh(booking)
        venue = db.get(Venue, booking.venue_id)
        result = _out(booking, event, venue, now)
        self._notify_staff(db, notifier, booking, event, venue)
        return result

    def hold_events(self, db: Session) -> list[HoldEventOut]:
        """US25 AC 1: the events Venue staff may hold a venue for, Approved or Planning, by name."""
        # DECISION-PENDING: D112 — Venue staff read no event requests (D55), so this lists only what a hold needs:
        # each bookable event's name, reference, status, schedule and expected attendance.
        # Only those with a coordinator, who alone can confirm or decline a hold (D20); an unassigned event's hold
        # would block the venue with nobody to act on it.
        events = db.scalars(
            select(Event)
            .where(Event.status.in_(BOOKABLE_STATUSES), Event.coordinator_id.is_not(None))
            .order_by(Event.name, Event.id)
        ).all()
        return [HoldEventOut.model_validate(event) for event in events]

    def make_primary(
        self, db: Session, coordinator: User, booking_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> VenueBookingOut:
        """US24 AC 4: the event's coordinator makes one of its live bookings the venue attendees see.
        Anyone else's booking is 404, as for withdraw."""
        # US25: a lapsed confirmed hold can't become the primary venue (D109).
        expire_lapsed_holds(db, now, notifier)
        found = db.get(VenueBooking, booking_id)
        if found is None:
            raise DomainError(404, "NOT_FOUND")
        # The event FOR UPDATE, as create locks it, so this and a first booking for the same event can't
        # both make a primary (D68).
        event = db.scalars(select(Event).where(Event.id == found.event_id).with_for_update()).one()
        if not may_book(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        booking = db.scalars(select(VenueBooking).where(VenueBooking.id == booking_id).with_for_update()).one()
        # DECISION-PENDING: D68 — only a live booking can be the primary venue.
        if booking.status not in LIVE_BOOKING_STATUSES:
            raise DomainError(409, "BOOKING_NOT_LIVE", status=booking.status.value)
        if not booking.is_primary:
            db.execute(
                update(VenueBooking)
                .where(
                    VenueBooking.event_id == event.id,
                    VenueBooking.id != booking.id,
                    VenueBooking.is_primary.is_(True),
                    VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
                )
                .values(is_primary=False, updated_at=now)
            )
            booking.is_primary = True
            booking.updated_at = now
            db.commit()
            db.refresh(booking)
        return _out(booking, event, db.get(Venue, booking.venue_id), now)

    def set_preparation(
        self, db: Session, staff: User, booking_id: uuid.UUID, body: BookingPreparationWrite, now: datetime
    ) -> VenueBookingOut:
        """US24 AC 7: Venue staff record how far they are with getting an approved venue ready."""
        # DECISION-PENDING: D73 — not_started, in_progress or ready, on an approved booking (CS3-49).
        value = body.preparation_status
        if value not in {status.value for status in PreparationStatus}:
            allowed = ", ".join(status.value for status in PreparationStatus)
            raise DomainError(
                422,
                "INVALID_BOOKING",
                fields=["preparation_status"],
                errors={"preparation_status": f"Choose one of: {allowed}."},
            )
        booking = db.scalars(select(VenueBooking).where(VenueBooking.id == booking_id).with_for_update()).one_or_none()
        if booking is None:
            raise DomainError(404, "NOT_FOUND")
        if booking.status != VenueBookingStatus.APPROVED:
            raise DomainError(409, "BOOKING_NOT_APPROVED", status=booking.status.value)
        booking.preparation_status = value
        booking.updated_at = now
        db.commit()
        db.refresh(booking)
        return _out(booking, db.get(Event, booking.event_id), db.get(Venue, booking.venue_id), now)

    def approve(
        self, db: Session, staff: User, booking_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> VenueBookingOut:
        """US4 AC 2, 3, 7: approves the request as a whole, which reserves the venue for the event.
        Refused, with no override, while the venue is booked or blocked for any part of the window
        with its buffers, once the start has passed, or above the venue's capacity; the request then
        stays pending, to be rejected or withdrawn."""
        # US25 AC 5: a confirmed hold must be approved before its expiry; past it, the sweep expires it and the
        # pending check below refuses it (BOOKING_NOT_PENDING, status expired).
        expire_lapsed_holds(db, now, notifier)
        # US23b (SCRUM-91), Chloe's #135 review: a replacement's original is locked with it, both by id, before the
        # event and the venue. Recording a block at the original's venue takes its bookings, then their events, then
        # the venue, so taking the original after the event could deadlock with it.
        replaces = db.scalar(select(VenueBooking.replaces_booking_id).where(VenueBooking.id == booking_id))
        if replaces is not None:
            db.execute(
                select(VenueBooking.id)
                .where(VenueBooking.id.in_([booking_id, replaces]))
                .order_by(VenueBooking.id)
                .with_for_update()
            ).all()
        booking = self._lock_pending(db, booking_id, staff)
        # Other pending requests don't expire, so one can still be waiting after its start;
        # approving it would reserve a window that's gone. Create refuses a past start too.
        if booking.starts_at <= now:
            raise DomainError(
                409, "BOOKING_EXPIRED", message="This request's start time has passed. It can only be rejected."
            )
        # The event FOR SHARE, as create reads it. The venue FOR UPDATE, so a buffer or capacity edit,
        # or a new request there (which reads it FOR SHARE), waits for the decision.
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
        # US13 AC 3, 5 (D32): the rule US13 built for this. The stored occupied window must fit the
        # opening hours now and clash with no live booking or block (bookings reported first).
        # DECISION-PENDING: D22 — blocks are checked here only, not by a constraint (see _insert).
        evaluation = evaluate_booking(db, booking)
        if evaluation.outside_hours is not None:
            raise _outside_hours(evaluation.outside_hours, evaluation.occupied, status_code=409)
        if evaluation.conflicts:
            raise _approval_unavailable(evaluation.conflicts[0], booking)
        changes = self._replace_original(db, booking, event, venue, now)
        result = self._decide(db, notifier, staff, booking, event, venue, VenueBookingStatus.APPROVED, now)
        for change in changes:
            # After the commit and best effort: a failure is logged and the replacement stands.
            try:
                notifier.venue_changed(**change)
            except Exception:
                logger.exception("could not tell %s their event's venue changed", change["email"])
        return result

    def _replace_original(
        self, db: Session, booking: VenueBooking, event: Event, venue: Venue, now: datetime
    ) -> list[dict[str, object]]:
        """US23b (SCRUM-91) AC 4 (D117): approving a replacement makes the booking it replaces Replaced, which frees
        its window and keeps its details, and moves the primary venue across. AC 7: attendees hear only when what
        they see, the primary venue or its times, changed. Returns those notices, to send after the commit."""
        if booking.replaces_booking_id is None:
            return []
        # Already locked by approve, before the event (Chloe's #135 review); read again under that lock.
        original = db.scalars(
            select(VenueBooking)
            .where(VenueBooking.id == booking.replaces_booking_id)
            .execution_options(populate_existing=True)
        ).one()
        # Withdrawn or restored meanwhile: nothing to replace, and this is one more venue for the event.
        if not _needs_rearrangement(original):
            return []
        primary = original.is_primary
        original_venue = db.get(Venue, original.venue_id)
        # AC 7: attendees see the primary venue. It is the replacement now if the original had it, or if the
        # coordinator already made the pending replacement primary (US24, Chloe's #135 review); either way they're
        # told when its venue or times differ from the original's.
        changed = (primary or booking.is_primary) and (
            original.venue_id != booking.venue_id
            or (original.starts_at, original.ends_at) != (booking.starts_at, booking.ends_at)
        )
        original.status = VenueBookingStatus.REPLACED
        original.replaced_at = now
        clear_restore_request(original)
        original.updated_at = now
        # The original leaves the live set first, so the one-primary index never sees two.
        db.flush()
        if primary:
            booking.is_primary = True
        if not changed:
            return []
        name = event.name or event.request_reference or str(event.id)
        emails = db.scalars(
            select(Registration.attendee_email)
            .where(Registration.event_id == event.id, Registration.status.in_(ACTIVE_STATUSES))
            .order_by(Registration.attendee_email)
        ).all()
        logger.info("venue for event %s moved from %s to %s", event.id, original_venue.name, venue.name)
        return [
            {
                "email": email,
                "event_id": event.id,
                "event_name": name,
                "venue_name": venue.name,
                "starts_at": booking.starts_at,
                "ends_at": booking.ends_at,
            }
            for email in dict.fromkeys(emails)
        ]

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
        # US25: a confirmed hold past its expiry lapses first, so it's Expired rather than rejected (D109).
        expire_lapsed_holds(db, now, notifier)
        booking = self._lock_pending(db, booking_id, staff)
        event = db.get(Event, booking.event_id)
        venue = db.get(Venue, booking.venue_id)
        # Set with the status in one flush: the notes alone on a pending booking break
        # venue_bookings_rejection_notes_only_when_rejected, and loading anything could autoflush them.
        booking.rejection_reason = reason
        booking.alternative_suggestion = alternative
        clear_restore_request(booking)
        return self._decide(db, notifier, staff, booking, event, venue, VenueBookingStatus.REJECTED, now)

    def _lock_pending(self, db: Session, booking_id: uuid.UUID, staff: User) -> VenueBooking:
        """The booking, locked FOR UPDATE so a decision and a withdrawal can't both land, once it's
        known that `staff` may decide it."""
        booking = db.scalars(
            select(VenueBooking).where(VenueBooking.id == booking_id).with_for_update()
        ).one_or_none()
        if booking is None:
            raise DomainError(404, "NOT_FOUND")
        # D51: not a booking they requested, nor one for an event they now coordinate. The first half
        # is also a CHECK (venue_bookings_decider_not_requester).
        event = db.get(Event, booking.event_id)
        refuse_self_decision(staff, created_by_user_id=booking.requested_by_user_id, event=event)
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
        result = _out(booking, event, venue, now)
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

    def pending(self, db: Session, now: datetime, notifier: Notifier) -> list[VenueBookingOut]:
        """Venue Staff's review queue (AC 4): Requested bookings, newest first (SCRUM-150). A confirmed hold carries its
        expiry, the time to approve it by (US25 AC 5)."""
        expire_lapsed_holds(db, now, notifier)
        rows = db.execute(
            select(VenueBooking, Event, Venue)
            .join(Event, Event.id == VenueBooking.event_id)
            .join(Venue, Venue.id == VenueBooking.venue_id)
            .where(VenueBooking.status == VenueBookingStatus.REQUESTED)
            .order_by(VenueBooking.created_at.desc(), VenueBooking.id)
        )
        return [_out(booking, event, venue, now) for booking, event, venue in rows]

    def evaluation(self, db: Session, booking_id: uuid.UUID) -> BookingEvaluationOut:
        """US13 AC 4 for Venue Staff (D36): what stands in the way of this booking now, each conflict
        with its overlap and reference, and any hours breach. US4 approves with the same rule."""
        booking = db.get(VenueBooking, booking_id)
        if booking is None:
            raise DomainError(404, "NOT_FOUND")
        return _evaluation_out(booking, evaluate_booking(db, booking))

    def for_event(
        self, db: Session, reader: User, event_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> EventVenueBookingsOut:
        """An event's bookings in every status, soonest first, with whether its venues are arranged.
        Venue Staff see any event's; a coordinator only one they may book (D20); since US24 the
        Organiser who created it, once the request is approved (D71). A draft is 404 to all (D11). Since US25 holds
        are listed too, and lapse first (D109)."""
        expire_lapsed_holds(db, now, notifier)
        event = db.get(Event, event_id)
        if event is None or event.status == EventStatus.DRAFT:
            raise DomainError(404, "NOT_FOUND")
        # DECISION-PENDING: D71 — the event's own Organiser reads its venues from approved on.
        organiser = (
            reader.holds(UserRole.ORGANISER)
            and event.created_by_user_id == reader.id
            and event.status in ORGANISER_VISIBLE_STATUSES
        )
        if not reader.holds(*VENUE_STAFF_ROLES) and not may_book(event, reader) and not organiser:
            raise DomainError(404, "NOT_FOUND")
        rows = db.execute(
            select(VenueBooking, Venue)
            .join(Venue, Venue.id == VenueBooking.venue_id)
            .where(VenueBooking.event_id == event_id)
            .order_by(VenueBooking.starts_at, VenueBooking.created_at, VenueBooking.id)
        ).all()
        live_pairs = [(booking, venue) for booking, venue in rows if booking.status in LIVE_BOOKING_STATUSES]
        live = [booking for booking, _ in live_pairs]
        primary = next((booking for booking in live if booking.is_primary), None)
        replacements = _replacements(db, [booking.id for booking, _ in rows if _needs_rearrangement(booking)])
        return EventVenueBookingsOut(
            bookings=[_out(booking, event, venue, now, replacements.get(booking.id)) for booking, venue in rows],
            venues_arranged=_arranged(event, live_pairs, now),
            primary_booking_id=primary.id if primary else None,
            allocated_attendees=sum(booking.expected_attendees for booking in live),
            expected_attendees=event.expected_attendees,
            next_action="choose_primary" if live and primary is None else None,
        )

    # --- US23b (SCRUM-91) AC 5: restoring a booking once its venue is free again (D118) ---

    def request_restore(
        self, db: Session, coordinator: User, booking_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> VenueBookingOut:
        """The event's coordinator asks Venue staff to restore a booking that needs rearrangement, once nothing
        overlaps its whole occupied window (setup and turnaround included). Anyone else's booking is 404."""
        expire_lapsed_holds(db, now, notifier)
        booking = db.scalars(select(VenueBooking).where(VenueBooking.id == booking_id).with_for_update()).one_or_none()
        event = db.get(Event, booking.event_id) if booking is not None else None
        if booking is None or event is None or not may_book(event, coordinator):
            raise DomainError(404, "NOT_FOUND")
        self._check_restorable(db, booking)
        if booking.restore_requested_at is not None:
            raise DomainError(409, "RESTORE_ALREADY_REQUESTED", message="Venue staff are already asked to restore it.")
        booking.restore_requested_at = now
        booking.restore_requested_by_user_id = coordinator.id
        # Asking again replaces Venue staff's last decline (Matt's #134 review).
        booking.restore_declined_at = None
        booking.restore_declined_by_user_id = None
        booking.restore_decline_reason = None
        booking.updated_at = now
        db.commit()
        db.refresh(booking)
        venue = db.get(Venue, booking.venue_id)
        result = _out(booking, event, venue, now)
        try:
            staff = db.scalars(
                select(User)
                .where(User.roles.any(UserRole.VENUE_STAFF), User.is_active.is_(True))
                .order_by(User.email)
            ).all()
            for member in staff:
                notifier.venue_restore_requested(
                    email=member.email,
                    booking_id=booking.id,
                    booking_reference=booking.reference,
                    event_name=event.name or event.request_reference or str(event.id),
                    venue_name=venue.name,
                    starts_at=booking.starts_at,
                    ends_at=booking.ends_at,
                )
        except Exception:
            logger.exception("could not tell Venue staff about the restore request for booking %s", booking.id)
        return result

    def restore_requests(self, db: Session, now: datetime, notifier: Notifier) -> list[VenueBookingOut]:
        """Venue staff's restore requests, oldest first."""
        expire_lapsed_holds(db, now, notifier)
        rows = db.execute(
            select(VenueBooking, Event, Venue)
            .join(Event, Event.id == VenueBooking.event_id)
            .join(Venue, Venue.id == VenueBooking.venue_id)
            .where(VenueBooking.restore_requested_at.is_not(None), VenueBooking.status.in_(BLOCKING_STATUSES))
            .order_by(VenueBooking.restore_requested_at, VenueBooking.id)
        )
        return [_out(booking, event, venue, now) for booking, event, venue in rows]

    def confirm_restore(
        self, db: Session, staff: User, booking_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> VenueBookingOut:
        """Venue staff confirm: checked again with the venue locked, so a block recorded meanwhile is seen, then
        the booking no longer needs rearrangement and keeps its status, window and primary."""
        booking, event = self._lock_restore(db, staff, booking_id, now, notifier)
        # D22: the venue FOR UPDATE, as recording a block locks it, so a new block waits or is seen.
        venue = db.scalars(select(Venue).where(Venue.id == booking.venue_id).with_for_update()).one()
        self._check_restorable(db, booking)
        booking.rearrangement_block_id = None
        booking.rearrangement_flagged_at = None
        return self._restore_decided(db, notifier, staff, booking, event, venue, "confirmed", None, now)

    def decline_restore(
        self, db: Session, staff: User, booking_id: uuid.UUID, body: RestoreDeclineWrite, now: datetime, notifier: Notifier
    ) -> VenueBookingOut:
        """Venue staff decline: the booking still needs rearrangement; the coordinator may ask again."""
        reason = body.reason.strip() or None if body.reason is not None else None
        booking, event = self._lock_restore(db, staff, booking_id, now, notifier)
        venue = db.get(Venue, booking.venue_id)
        return self._restore_decided(db, notifier, staff, booking, event, venue, "declined", reason, now)

    def _check_restorable(self, db: Session, booking: VenueBooking) -> None:
        if not _needs_rearrangement(booking):
            raise DomainError(409, "BOOKING_NOT_REPLACEABLE", status=booking.status.value, message="This booking doesn't need rearrangement.")
        replacement = _replacements(db, [booking.id]).get(booking.id)
        if replacement is not None:
            reference = db.get(VenueBooking, replacement).reference
            raise DomainError(
                409,
                "REPLACEMENT_EXISTS",
                reference=reference,
                message=f"Booking {reference} is its replacement. Withdraw that request before restoring this one.",
            )
        # The whole occupied window, every block at the venue: not only the one that marked it (Matt's #131 review).
        conflicts = block_conflicts(db, booking.venue_id, Window(booking.occupied_starts_at, booking.occupied_ends_at))
        if conflicts:
            raise _unavailable(conflicts[0], Window(booking.occupied_starts_at, booking.occupied_ends_at))

    def _lock_restore(
        self, db: Session, staff: User, booking_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> tuple[VenueBooking, Event]:
        expire_lapsed_holds(db, now, notifier)
        booking = db.scalars(select(VenueBooking).where(VenueBooking.id == booking_id).with_for_update()).one_or_none()
        if booking is None:
            raise DomainError(404, "NOT_FOUND")
        event = db.get(Event, booking.event_id)
        # D51: not one they asked for, nor for an event they coordinate.
        refuse_self_decision(staff, created_by_user_id=booking.restore_requested_by_user_id, event=event)
        if booking.restore_requested_at is None or not _needs_rearrangement(booking):
            raise DomainError(409, "RESTORE_NOT_REQUESTED", status=booking.status.value)
        return booking, event

    def _restore_decided(
        self,
        db: Session,
        notifier: Notifier,
        staff: User,
        booking: VenueBooking,
        event: Event,
        venue: Venue,
        decision: RestoreDecision,
        reason: str | None,
        now: datetime,
    ) -> VenueBookingOut:
        asked_by = booking.restore_requested_by_user_id
        clear_restore_request(booking)
        # Matt's #134 review: a decline is kept, with who and why, so the coordinator sees it until they ask again;
        # a restore leaves nothing to show.
        declined = decision == "declined"
        booking.restore_declined_at = now if declined else None
        booking.restore_declined_by_user_id = staff.id if declined else None
        booking.restore_decline_reason = reason if declined else None
        booking.updated_at = now
        db.commit()
        db.refresh(booking)
        result = _out(booking, event, venue, now)
        # The coordinator who asked, and the event's coordinator if that's someone else now, once each.
        try:
            recipients = db.scalars(
                select(User)
                .where(User.id.in_({asked_by, event.coordinator_id} - {None}), User.is_active.is_(True))
                .order_by(User.email)
            ).all()
            for user in recipients:
                notifier.venue_restore_decided(
                    email=user.email,
                    booking_id=booking.id,
                    booking_reference=booking.reference,
                    event_name=event.name or event.request_reference or str(event.id),
                    venue_name=venue.name,
                    decision=decision,
                    reason=reason,
                )
        except Exception:
            logger.exception("could not tell the coordinator about the restore decision for booking %s", booking.id)
        return result

    def _commit(self, db: Session, venue: Venue, starts_at: datetime, ends_at: datetime) -> None:
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint == ONE_LIVE_REPLACEMENT:
                # D117: another replacement for the same booking committed first.
                raise DomainError(
                    409, "REPLACEMENT_EXISTS", message="This booking already has a replacement waiting or approved."
                ) from None
            if constraint == NO_OVERLAP:
                # AC 7: another request for an overlapping window committed first. It's visible now.
                evaluation = evaluate_window(db, venue, starts_at, ends_at)
                raise _unavailable(_first_booking_conflict(evaluation), evaluation.occupied) from None
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
                .where(User.roles.any(UserRole.VENUE_STAFF), User.is_active.is_(True))
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


    def _notify_staff_withdrawn(
        self, db: Session, notifier: Notifier, booking: VenueBooking, event: Event, venue: Venue
    ) -> None:
        """US24 (D69): every active Venue Staff member hears that a venue they approved is free again.
        Runs after the commit; a failure is logged and the withdrawal stands."""
        try:
            staff = db.scalars(
                select(User)
                .where(User.roles.any(UserRole.VENUE_STAFF), User.is_active.is_(True))
                .order_by(User.email)
            ).all()
            event_name = event.name or event.request_reference or str(event.id)
            for member in staff:
                notifier.venue_booking_withdrawn(
                    email=member.email,
                    booking_id=booking.id,
                    event_name=event_name,
                    venue_name=venue.name,
                    starts_at=booking.starts_at,
                    ends_at=booking.ends_at,
                )
        except Exception:
            logger.exception("could not notify Venue Staff about withdrawn venue booking %s", booking.id)


booking_service = VenueBookingService()
