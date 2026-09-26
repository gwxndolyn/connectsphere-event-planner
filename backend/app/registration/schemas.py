from datetime import datetime

from pydantic import BaseModel

from app.registration.models import RegistrationStatus


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
