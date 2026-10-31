import uuid
from datetime import datetime

from pydantic import BaseModel

from app.event.models import DeliveryMode, EventStatus
from app.event.schemas import RegistrationFieldOut
from app.registration.models import RegistrationStatus


class RegisterRequest(BaseModel):
    answers: dict[str, str] = {}


class EventConfirmationOut(BaseModel):
    """The AC requires date, time and venue in the confirmation. For an online event,
    `join_link` stands in for venue (spec §3)."""

    name: str
    start_at: datetime
    end_at: datetime
    venue_name: str | None = None
    join_link: str | None = None


class RegisterResponse(BaseModel):
    registration_id: uuid.UUID
    status: RegistrationStatus
    event: EventConfirmationOut


class WaitlistJoinResponse(BaseModel):
    registration_id: uuid.UUID
    status: RegistrationStatus
    position: int


class WithdrawResponse(BaseModel):
    status: RegistrationStatus
    withdrawn_at: datetime
    event_name: str
    seats_remaining: int


class OfferReleaseResponse(BaseModel):
    """Result of an offer being expired or declined. `offer_passed_on` says whether the seat
    went to the next person — not who, since no endpoint may reveal another attendee (TC-X-04)."""

    status: RegistrationStatus
    event_name: str
    seats_remaining: int
    offer_passed_on: bool


class MyRegistrationOut(BaseModel):
    """One row of `GET /me/registrations` (spec §3). `joining_info` is the room number for an
    in-person event or the join link for an online one (TC-US11-02, TC-US11-03) — the mockup
    renders this field directly and must not re-derive it from `delivery_mode`."""

    registration_id: uuid.UUID
    # Lets the events board match a row to `GET /events/available` (SCRUM-79).
    event_id: uuid.UUID
    event_name: str
    date: str
    start_time: str
    end_time: str
    venue_name: str | None = None
    joining_info: str
    delivery_mode: DeliveryMode


class MyWaitlistedRegistrationOut(MyRegistrationOut):
    waitlist_position: int


class MyOfferedRegistrationOut(MyRegistrationOut):
    """A place held for this attendee after a withdrawal (US6b). Accept it with
    `POST /registrations/{registration_id}/accept` before `offer_expires_at`."""

    offer_expires_at: datetime


class MyRegistrationsResponse(BaseModel):
    confirmed: list[MyRegistrationOut]
    waitlisted: list[MyWaitlistedRegistrationOut]
    # Additive in Sprint 2 (SCRUM-50): older clients that read only the two lists above still work.
    offered: list[MyOfferedRegistrationOut] = []


class ManagedEventOut(BaseModel):
    """An event whose registrations the caller may view (US28 AC 1)."""

    id: uuid.UUID
    name: str
    start_at: datetime
    end_at: datetime
    status: EventStatus
    capacity: int


class ManagedEventsResponse(BaseModel):
    events: list[ManagedEventOut]


class RegistrationTotalsOut(BaseModel):
    """US28 AC 2. Counted over every registration, whatever the list's filter."""

    confirmed: int
    waitlisted: int
    offered: int
    seats_remaining: int


class EventRegistrantOut(BaseModel):
    """One registrant (US28 AC 3). `attendee_name` is the user's `full_name`, null for seeded users
    and email-only waitlist entries (D3)."""

    registration_id: uuid.UUID
    attendee_name: str | None
    attendee_email: str
    status: RegistrationStatus
    registered_at: datetime
    waitlist_position: int | None = None
    offer_expires_at: datetime | None = None
    # Keyed by `field_key`; a field the registrant didn't answer is absent.
    answers: dict[str, str | None]


class EventRegistrationsResponse(BaseModel):
    event: ManagedEventOut
    totals: RegistrationTotalsOut
    # The event's registration questions, in order, so the screen can label `answers`.
    registration_fields: list[RegistrationFieldOut]
    registrations: list[EventRegistrantOut]
