import uuid
from datetime import datetime

from sqlalchemy import Text, cast, exists, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.user.models import User, UserRole
from app.venue.models import (
    ACCESSIBILITY_FEATURES,
    FACILITIES,
    LIVE_BOOKING_STATUSES,
    ROOM_LAYOUTS,
    Venue,
    VenueBooking,
    VenueBookingStatus,
)
from app.venue.schemas import VenueOut, VenueWrite

# DECISION-PENDING: D19 — Venue Staff arrives with US16b (SCRUM-82), which adds the enum value.
# Until then operations_manager stands in, so this user can also read the event-request queue
# (D11). US16b changes this one line to (UserRole.VENUE_STAFF,).
VENUE_STAFF_ROLES = (UserRole.OPERATIONS_MANAGER,)

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
    """Whether the reader requested a Requested or Approved booking at this venue, so they can
    still open it after it's deactivated (US20's gap, closed in US22, TC-US22-16)."""
    # DECISION-PENDING: D20 — until US10a assigns coordinators to events, "whose event is booked
    # here" means "who requested the booking". US10a widens this to the reader's assigned events.
    return db.scalar(
        select(
            exists().where(
                VenueBooking.venue_id == venue_id,
                VenueBooking.requested_by_user_id == reader.id,
                VenueBooking.status.in_(LIVE_BOOKING_STATUSES),
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


class VenueService:
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
        if reader.role not in VENUE_STAFF_ROLES:
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
            venue.is_active or reader.role in VENUE_STAFF_ROLES or _has_live_booking_by(db, venue.id, reader)
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

        for field in changes:
            setattr(venue, field, cleaned[field])
        self._commit(db)
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

    def _commit(self, db: Session) -> None:
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            field = CONSTRAINT_FIELDS.get(constraint)
            if field is None:
                raise
            raise _invalid({field: f"Invalid value for {field.replace('_', ' ')}."}) from None


venue_service = VenueService()
