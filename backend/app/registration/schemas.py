import uuid
from datetime import datetime

from pydantic import BaseModel

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


class WaitlistJoinRequest(BaseModel):
    email: str


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
