import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.event.models import Event
from app.notification.service import HoldStage, Notifier
from app.user.models import User
from app.venue.models import Venue, VenueBooking, VenueBookingStatus, clear_restore_request

logger = logging.getLogger(__name__)

# DECISION-PENDING: D108 — a hold lasts at most 14 days; D109 — the coordinator is warned in its last 24 hours.
HOLD_MAX_LENGTH = timedelta(days=14)
HOLD_WARNING = timedelta(hours=24)
# A hold, and a hold confirmed into a request that Venue staff haven't decided yet (AC 5), lapse at the expiry.
LAPSING_STATUSES = (VenueBookingStatus.HELD, VenueBookingStatus.REQUESTED)


@dataclass
class _Notice:
    email: str
    booking_id: uuid.UUID
    event_name: str
    venue_name: str
    starts_at: datetime
    ends_at: datetime
    expires_at: datetime
    stage: HoldStage


def notice_for(db: Session, booking: VenueBooking, stage: HoldStage) -> _Notice | None:
    """What the event's coordinator is told about this hold (AC 4), read inside the transaction. None when the
    event has no active coordinator to tell."""
    event = db.get(Event, booking.event_id)
    coordinator = db.get(User, event.coordinator_id) if event is not None and event.coordinator_id else None
    if coordinator is None or not coordinator.is_active:
        logger.warning("could not tell anyone that hold %s is %s: no active coordinator", booking.id, stage)
        return None
    venue = db.get(Venue, booking.venue_id)
    return _Notice(
        email=coordinator.email,
        booking_id=booking.id,
        event_name=event.name or event.request_reference or str(event.id),
        venue_name=venue.name,
        starts_at=booking.starts_at,
        ends_at=booking.ends_at,
        expires_at=booking.hold_expires_at,
        stage=stage,
    )


def send(notifier: Notifier, notice: _Notice | None) -> None:
    """After the commit and best effort, as the other notices: a failure is logged and the change stands."""
    if notice is None:
        return
    try:
        notifier.venue_held(
            email=notice.email,
            booking_id=notice.booking_id,
            event_name=notice.event_name,
            venue_name=notice.venue_name,
            starts_at=notice.starts_at,
            ends_at=notice.ends_at,
            expires_at=notice.expires_at,
            stage=notice.stage,
        )
    except Exception:
        logger.exception("could not send the %s notice for hold %s", notice.stage, notice.booking_id)


def _lapsed(booking: VenueBooking, now: datetime) -> bool:
    return booking.status in LAPSING_STATUSES and booking.hold_expires_at is not None and booking.hold_expires_at <= now


def _due_warning(booking: VenueBooking, now: datetime) -> bool:
    return (
        booking.status == VenueBookingStatus.HELD
        and booking.hold_warned_at is None
        and booking.hold_expires_at is not None
        and booking.hold_expires_at - HOLD_WARNING <= now < booking.hold_expires_at
    )


def expire_lapsed_holds(db: Session, now: datetime, notifier: Notifier) -> int:
    """DECISION-PENDING: D109 — lapse on read, as waitlist offers (D2, SCRUM-137; §1a "Lapse on read"). Every read or
    change of venue bookings calls this first: a hold past its expiry, or a confirmed one Venue staff haven't
    approved by then (AC 5), becomes Expired and frees the window (AC 3); one inside its last 24 hours warns its
    coordinator, once (AC 4).

    1. A cheap check without a lock. The usual answer is "nothing due": no lock, no write.
    2. Each booking found, in id order, in its own transaction: lock it, re-check under the lock (another request
       may have got there first), apply the change, commit. One lock at a time in a fixed order, so two reads
       can't deadlock.
    3. It commits on its own, before the caller's work, so a refusal that follows can't roll the change back.

    Returns how many holds it expired."""
    due = db.scalars(
        select(VenueBooking.id).where(
            VenueBooking.hold_expires_at.is_not(None),
            or_(
                and_(VenueBooking.status.in_(LAPSING_STATUSES), VenueBooking.hold_expires_at <= now),
                and_(
                    VenueBooking.status == VenueBookingStatus.HELD,
                    VenueBooking.hold_warned_at.is_(None),
                    VenueBooking.hold_expires_at <= now + HOLD_WARNING,
                ),
            ),
        )
    ).all()

    expired = 0
    for booking_id in sorted(due):
        booking = db.scalars(
            select(VenueBooking)
            .where(VenueBooking.id == booking_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        notice = None
        if _lapsed(booking, now):
            clear_restore_request(booking)
            booking.status = VenueBookingStatus.EXPIRED
            booking.expired_at = now
            # A confirmed hold may have become the event's primary venue; an expired one can't stay it (AC 6).
            booking.is_primary = False
            booking.updated_at = now
            expired += 1
            notice = notice_for(db, booking, "expired")
        elif _due_warning(booking, now):
            booking.hold_warned_at = now
            notice = notice_for(db, booking, "expiring")
        db.commit()
        send(notifier, notice)
    return expired
