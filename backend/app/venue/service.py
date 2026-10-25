import uuid
from collections.abc import Callable
from types import SimpleNamespace
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import Date, DateTime, Text, and_, cast, exists, func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.models import Event
from app.user.models import User, UserRole
from app.venue.availability import Window, hours_breach
from app.venue.models import (
    ACCESSIBILITY_FEATURES,
    FACILITIES,
    LIVE_BOOKING_STATUSES,
    ROOM_LAYOUTS,
    Venue,
    VenueBlock,
    VenueBooking,
    VenueBookingStatus,
    occupied_window,
)
from app.venue.schemas import VenueOut, VenueSearchCriteria, VenueSearchOut, VenueWrite

# DECISION-PENDING: D49 — US16b (SCRUM-119) made Venue Staff a real role, retiring D19's
# operations_manager stand-in.
VENUE_STAFF_ROLES = (UserRole.VENUE_STAFF,)

# DECISION-PENDING: D25 — US2 is the Event Coordinator's story. Coordinators search, and so do
# Venue Staff. Organisers and attendees get 403.
VENUE_SEARCH_ROLES = (UserRole.COORDINATOR, UserRole.VENUE_STAFF)
SEARCH_REQUIRED_FIELDS = ("date", "start_time", "end_time", "attendees")
# Every venue and requested time is Singapore wall-clock (D9, TC-X-01).
VENUE_TIMEZONE = ZoneInfo("Asia/Singapore")

REQUIRED_FIELDS = ("name", "location", "capacity", "opens_at", "closes_at")
BUFFER_FIELDS = ("setup_minutes", "turnaround_minutes")
# D18's vocabularies, with the words an error message uses for each list.
TAG_FIELDS = {
    "facilities": (FACILITIES, "facilities"),
    "accessibility_features": (ACCESSIBILITY_FEATURES, "accessibility features"),
    "room_layouts": (ROOM_LAYOUTS, "room layouts"),
}
# Backstop for anything the checks below miss: each named CHECK in the migration maps to its field.
CONSTRAINT_FIELDS = {
    "venues_name_not_blank": "name",
    "venues_location_not_blank": "location",
    "venues_capacity_positive": "capacity",
    "venues_hours_valid": "closes_at",
    "venues_setup_minutes_non_negative": "setup_minutes",
    "venues_turnaround_minutes_non_negative": "turnaround_minutes",
}
BUFFERS_LOCKED_MESSAGE = "Setup and turnaround can't change while this venue has approved future bookings."
BUFFERS_CONFLICT_MESSAGE = (
    "With these setup and turnaround times, requested bookings at this venue would overlap or run outside "
    "its opening hours. Change the times, or ask the coordinators to change or withdraw those requests."
)
NO_OVERLAP = "venue_bookings_no_overlap"


def has_approved_future_bookings(db: Session, venue_id: uuid.UUID, now: datetime) -> bool:
    """Whether the venue has approved bookings that haven't finished, which lock its buffers
    (US20 AC 2). A booking under way counts. Requested ones don't: US4 hasn't approved them."""
    return db.scalar(
        select(
            exists().where(
                VenueBooking.venue_id == venue_id,
                VenueBooking.status == VenueBookingStatus.APPROVED,
                VenueBooking.ends_at > now,
            )
        )
    )


def _has_live_booking_by(db: Session, venue_id: uuid.UUID, reader: User) -> bool:
    """Whether an event assigned to the reader has a Requested or Approved booking at this venue,
    so they can still open it after it's deactivated (US20's gap, closed in US22, TC-US22-16)."""
    # DECISION-PENDING: D20 — since US10a (SCRUM-13), "whose event is booked here" is the event's
    # assigned coordinator (events.coordinator_id), whoever made the request.
    return db.scalar(
        select(
            exists().where(
                VenueBooking.venue_id == venue_id,
                VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
                Event.id == VenueBooking.event_id,
                Event.coordinator_id == reader.id,
            )
        )
    )


def _invalid(errors: dict[str, str]) -> DomainError:
    return DomainError(422, "INVALID_VENUE", fields=list(errors), errors=errors)


def _clean_tags(field: str, values: list[str], errors: dict[str, str], vocabulary: str | None = None) -> list[str]:
    """Trimmed, de-duplicated and in D18's order; the database doesn't reject duplicates.
    `vocabulary` names the TAG_FIELDS list when `field` isn't a venue column (a booking's tags)."""
    allowed, label = TAG_FIELDS[vocabulary or field]
    given = list(dict.fromkeys(value.strip() for value in values))
    unknown = [value for value in given if value not in allowed]
    if unknown:
        errors[field] = f"Unknown {label}: {', '.join(unknown)}. Allowed: {', '.join(allowed)}."
    return [tag for tag in allowed if tag in given]


def _validate(values: dict[str, object]) -> dict[str, object]:
    """Checks a whole venue (the merged values on edit) against the table's CHECKs, collecting every
    invalid field so the form can mark them all at once. Returns the values with text trimmed and
    tags cleaned."""
    errors: dict[str, str] = {}
    cleaned = dict(values)
    for field, label in (("name", "Name"), ("location", "Location")):
        cleaned[field] = str(values[field]).strip()
        if not cleaned[field]:
            errors[field] = f"{label} can't be blank."
    if values["capacity"] <= 0:
        errors["capacity"] = "Capacity must be greater than 0."
    if values["closes_at"] <= values["opens_at"]:
        errors["closes_at"] = "Closing time must be after opening time (hours can't cross midnight)."
    for field, label in (("setup_minutes", "Setup minutes"), ("turnaround_minutes", "Turnaround minutes")):
        if values[field] < 0:
            errors[field] = f"{label} can't be negative. 0 is allowed."
    for field in TAG_FIELDS:
        cleaned[field] = _clean_tags(field, values[field], errors)
    if errors:
        raise _invalid(errors)
    return cleaned


def _whole_number(value: int | str) -> int | None:
    """An attendance as an int, or None when it isn't a whole number (1.5, 1e3, "lots")."""
    if isinstance(value, int):
        return value
    text = value.strip()
    return int(text) if text.lstrip("-").isdigit() else None


def _slot(model: type[VenueBooking] | type[VenueBlock]):
    """A booking's or block's half-open time range, as its GiST index stores it."""
    return func.tstzrange(model.starts_at, model.ends_at, literal("[)"))


def _occupied_slot():
    """A booking's stored occupied window, as venue_bookings_no_overlap's GiST index stores it (US13)."""
    return func.tstzrange(VenueBooking.occupied_starts_at, VenueBooking.occupied_ends_at, literal("[)"))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class VenueService:
    def find_available(
        self,
        db: Session,
        now: datetime,
        *,
        on: date | None,
        start_time: time | None,
        end_time: time | None,
        attendees: int | str | None,
        location: str | None = None,
        facilities: list[str] | None = None,
        accessibility: list[str] | None = None,
    ) -> VenueSearchOut:
        """US2 (SCRUM-7): active venues that can host this event: big enough (AC 4), open for the
        whole time (AC 6), with no live booking (US22's LIVE_BOOKING_STATUSES: requested or
        approved) and no block overlapping it (AC 5), and every given filter matched (AC 2).
        Smallest suitable venue first, then by name. One query, for AC 8's 3 seconds."""
        given = {"date": on, "start_time": start_time, "end_time": end_time, "attendees": attendees}
        missing = [field for field in SEARCH_REQUIRED_FIELDS if given[field] is None or given[field] == ""]
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)

        errors: dict[str, str] = {}
        attendees = _whole_number(attendees)
        if on < now.astimezone(VENUE_TIMEZONE).date():
            errors["date"] = "The date can't be in the past."
        if end_time <= start_time:
            errors["end_time"] = "The end time must be after the start time (events can't cross midnight)."
        if attendees is None:
            errors["attendees"] = "Expected attendance must be a whole number."
        elif attendees < 1:
            errors["attendees"] = "Expected attendance must be at least 1."
        tags: dict[str, list[str]] = {}
        for param, field, values in (
            ("facilities", "facilities", facilities),
            ("accessibility", "accessibility_features", accessibility),
        ):
            field_errors: dict[str, str] = {}
            tags[param] = _clean_tags(field, values or [], field_errors)
            if field_errors:
                errors[param] = field_errors[field]
        if errors:
            raise DomainError(422, "INVALID_VENUE_SEARCH", fields=list(errors), errors=errors)

        location = location.strip() if location and location.strip() else None
        starts_at = datetime.combine(on, start_time, VENUE_TIMEZONE)
        ends_at = datetime.combine(on, end_time, VENUE_TIMEZONE)

        # DECISION-PENDING: D26 — US13: a venue is offered only if the window its own buffers make it
        # occupy for this time, [start - setup, end + turnaround), is free and inside its hours. Built
        # per venue in SQL, so it's still one query (AC 8). Half-open like venue_bookings_no_overlap:
        # windows that only touch don't clash. Requested blocks as well as approved (US22's D21).
        # The overlap is written as && on ranges, the expressions both GiST indexes hold: a booking's
        # stored occupied window (the exclusion constraint's) and a block's plain one (blocks have no
        # buffers of their own). Two comparisons on the ends mean the same but can't use them.
        # Cast, so the timestamp is typed even when the statement is rendered with its values inline.
        occupied_from = cast(literal(starts_at), DateTime(timezone=True)) - func.make_interval(0, 0, 0, 0, 0, Venue.setup_minutes)
        occupied_to = cast(literal(ends_at), DateTime(timezone=True)) + func.make_interval(0, 0, 0, 0, 0, Venue.turnaround_minutes)
        window = func.tstzrange(occupied_from, occupied_to, literal("[)"))
        # AC 5 as instants on the searched day, so a setup before midnight or a turnaround past it is
        # outside the hours too (US20 hours can't cross midnight).
        opens = func.timezone(literal("Asia/Singapore"), cast(literal(on), Date) + Venue.opens_at)
        closes = func.timezone(literal("Asia/Singapore"), cast(literal(on), Date) + Venue.closes_at)
        # OFFSET 0 keeps each EXISTS a per-venue subplan: the window depends on the venue's buffers, and
        # flattened into an anti-join Postgres would scan every booking and block instead of using
        # the GiST indexes for that venue (AC 8, TC-US2-08).
        booked = exists(
            select(VenueBooking.id)
            .where(
                VenueBooking.venue_id == Venue.id,
                VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
                _occupied_slot().op("&&")(window),
            )
            .offset(0)
        )
        blocked = exists(
            select(VenueBlock.id)
            .where(VenueBlock.venue_id == Venue.id, _slot(VenueBlock).op("&&")(window))
            .offset(0)
        )
        query = select(Venue).where(
            Venue.is_active.is_(True),
            Venue.capacity >= attendees,
            occupied_from >= opens,
            occupied_to <= closes,
            ~booked,
            ~blocked,
        )
        if location:
            query = query.where(Venue.location.ilike(f"%{_escape_like(location)}%", escape="\\"))
        if tags["facilities"]:
            query = query.where(Venue.facilities.op("@>")(cast(tags["facilities"], ARRAY(Text))))
        if tags["accessibility"]:
            query = query.where(Venue.accessibility_features.op("@>")(cast(tags["accessibility"], ARRAY(Text))))

        venues = db.scalars(query.order_by(Venue.capacity, Venue.name, Venue.id))
        return VenueSearchOut(
            venues=[VenueOut.model_validate(venue) for venue in venues],
            criteria=VenueSearchCriteria(
                date=on,
                start_time=start_time,
                end_time=end_time,
                attendees=attendees,
                location=location,
                facilities=tags["facilities"],
                accessibility=tags["accessibility"],
            ),
        )

    def search(
        self,
        db: Session,
        reader: User,
        *,
        q: str | None = None,
        min_capacity: int | None = None,
        facilities: list[str] | None = None,
        accessibility: list[str] | None = None,
        active: bool | None = None,
    ) -> list[VenueOut]:
        """Venues by name. Only staff see inactive ones; `active` narrows staff's list and is
        ignored for everyone else, who always get active venues."""
        query = select(Venue)
        if not reader.holds(*VENUE_STAFF_ROLES):
            query = query.where(Venue.is_active.is_(True))
        elif active is not None:
            query = query.where(Venue.is_active.is_(active))
        if q and q.strip():
            pattern = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.where(Venue.name.ilike(f"%{pattern}%", escape="\\"))
        if min_capacity is not None:
            query = query.where(Venue.capacity >= min_capacity)

        errors: dict[str, str] = {}
        for param, field, column, values in (
            ("facilities", "facilities", Venue.facilities, facilities),
            ("accessibility", "accessibility_features", Venue.accessibility_features, accessibility),
        ):
            if values:
                field_errors: dict[str, str] = {}
                tags = _clean_tags(field, values, field_errors)
                if field_errors:
                    errors[param] = field_errors[field]
                # Every given tag must be present (`@>`).
                query = query.where(column.op("@>")(cast(tags, ARRAY(Text))))
        if errors:
            raise _invalid(errors)

        venues = db.scalars(query.order_by(Venue.name, Venue.id))
        return [VenueOut.model_validate(venue) for venue in venues]

    def get(self, db: Session, venue_id: uuid.UUID, reader: User) -> VenueOut:
        venue = db.get(Venue, venue_id)
        visible = venue is not None and (
            venue.is_active or reader.holds(*VENUE_STAFF_ROLES) or _has_live_booking_by(db, venue.id, reader)
        )
        if not visible:
            raise DomainError(404, "NOT_FOUND")
        return VenueOut.model_validate(venue)

    def create(self, db: Session, body: VenueWrite) -> VenueOut:
        values = body.model_dump()
        missing = [field for field in REQUIRED_FIELDS if values[field] is None]
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)
        # Left out (or null) tags and buffers take the columns' defaults.
        for field in TAG_FIELDS:
            values[field] = values[field] or []
        for field in BUFFER_FIELDS:
            values[field] = 0 if values[field] is None else values[field]

        venue = Venue(**_validate(values))
        db.add(venue)
        self._commit(db)
        db.refresh(venue)
        return VenueOut.model_validate(venue)

    def update(self, db: Session, venue_id: uuid.UUID, body: VenueWrite, now: datetime) -> VenueOut:
        """Changes only the fields sent, on active or inactive venues alike (staff may fix details
        before reactivating). Validates the venue as it would be after the edit."""
        venue = self._locked(db, venue_id)
        changes = body.model_dump(exclude_unset=True)
        # Every column is NOT NULL, so null is never a valid edit.
        missing = [field for field, value in changes.items() if value is None]
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)

        current = {field: getattr(venue, field) for field in VenueWrite.model_fields}
        cleaned = _validate(current | changes)

        # Resending the stored value (a form posting every field) isn't a buffer edit.
        buffer_edits = [field for field in BUFFER_FIELDS if field in changes and changes[field] != current[field]]
        if buffer_edits and has_approved_future_bookings(db, venue.id, now):
            raise DomainError(409, "VENUE_BUFFERS_LOCKED", fields=buffer_edits, message=BUFFERS_LOCKED_MESSAGE)
        recomputed = self._recompute_windows(db, venue, cleaned, buffer_edits, now) if buffer_edits else {}

        for field in changes:
            setattr(venue, field, cleaned[field])
        if recomputed:
            # venue_bookings_no_overlap is checked row by row, so a new window can clash with another
            # booking's old one (buffers swapping sides between touching bookings, PR #79 review).
            # Shrink every recomputed window to its booking's own times first, which can't overlap
            # (any overlap there would already overlap the stored windows), then widen them.
            for booking in recomputed:
                booking.occupied_starts_at, booking.occupied_ends_at = booking.starts_at, booking.ends_at
            self._flush(db, buffer_edits)
            for booking, (starts_at, ends_at) in recomputed.items():
                booking.occupied_starts_at, booking.occupied_ends_at = starts_at, ends_at
        self._commit(db, buffer_edits)
        db.refresh(venue)
        return VenueOut.model_validate(venue)

    def set_active(self, db: Session, venue_id: uuid.UUID, active: bool) -> VenueOut:
        """Deactivate or reactivate. Idempotent. A deactivated venue leaves non-staff lists and US2's
        search; bookings at it are kept (AC 3)."""
        venue = self._locked(db, venue_id)
        venue.is_active = active
        self._commit(db)
        db.refresh(venue)
        return VenueOut.model_validate(venue)

    def _locked(self, db: Session, venue_id: uuid.UUID) -> Venue:
        venue = db.scalars(select(Venue).where(Venue.id == venue_id).with_for_update()).one_or_none()
        if venue is None:
            raise DomainError(404, "NOT_FOUND")
        return venue

    def _recompute_windows(
        self, db: Session, venue: Venue, after: dict[str, object], buffer_edits: list[str], now: datetime
    ) -> dict[VenueBooking, tuple[datetime, datetime]]:
        """DECISION-PENDING: D31 — a buffer edit is allowed while only Requested future bookings
        exist (AC 6 locks it for approved ones), so their stored occupied windows are recomputed with
        the venue as it will be. The edit is refused, with nothing saved, if any would then overlap
        another live booking or run outside opening hours (AC 3, 5). Past bookings keep their windows.
        The venue row is already locked FOR UPDATE, so no request can slip in meanwhile."""
        changed = SimpleNamespace(**after)  # occupied_window and hours_breach read only the buffers and hours
        live = db.scalars(
            select(VenueBooking)
            .where(VenueBooking.venue_id == venue.id, VenueBooking.status.in_(LIVE_BOOKING_STATUSES))
            .with_for_update()
        ).all()
        affected = [b for b in live if b.status == VenueBookingStatus.REQUESTED and b.ends_at > now]
        windows = {b: occupied_window(changed, b.starts_at, b.ends_at) for b in affected}
        current = {b: (b.occupied_starts_at, b.occupied_ends_at) for b in live if b not in windows}
        every = {**current, **windows}

        clashing: dict[VenueBooking, str] = {}
        for booking, (starts_at, ends_at) in windows.items():
            if hours_breach(changed, booking.starts_at, Window(starts_at, ends_at)) is not None:
                clashing.setdefault(booking, "hours")
            for other, (other_starts, other_ends) in every.items():
                if other is not booking and starts_at < other_ends and other_starts < ends_at:
                    clashing.setdefault(booking, "overlap")
                    clashing.setdefault(other, "overlap")
        if clashing:
            raise DomainError(
                409,
                "VENUE_BUFFERS_CONFLICT",
                fields=buffer_edits,
                bookings=[
                    {
                        "reference": booking.reference,
                        "starts_at": booking.starts_at.isoformat(),
                        "ends_at": booking.ends_at.isoformat(),
                        "occupied": Window(*every[booking]).as_json(),
                        "reason": reason,
                    }
                    for booking, reason in sorted(clashing.items(), key=lambda item: item[0].starts_at)
                ],
                message=BUFFERS_CONFLICT_MESSAGE,
            )
        return windows

    def _commit(self, db: Session, buffer_edits: list[str] | None = None) -> None:
        self._write(db, db.commit, buffer_edits)

    def _flush(self, db: Session, buffer_edits: list[str] | None = None) -> None:
        self._write(db, db.flush, buffer_edits)

    def _write(self, db: Session, write: Callable[[], None], buffer_edits: list[str] | None) -> None:
        try:
            write()
        except IntegrityError as error:
            db.rollback()
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint == NO_OVERLAP:
                # Backstop for _recompute_windows: the exclusion constraint refused a recomputed window.
                raise DomainError(
                    409, "VENUE_BUFFERS_CONFLICT", fields=buffer_edits or [], bookings=[], message=BUFFERS_CONFLICT_MESSAGE
                ) from None
            field = CONSTRAINT_FIELDS.get(constraint)
            if field is None:
                raise
            raise _invalid({field: f"Invalid value for {field.replace('_', ' ')}."}) from None


venue_service = VenueService()
