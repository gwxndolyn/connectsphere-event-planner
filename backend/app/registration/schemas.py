from datetime import datetime

from pydantic import BaseModel

from app.registration.models import RegistrationStatus


class WithdrawResponse(BaseModel):
    status: RegistrationStatus
    withdrawn_at: datetime
    event_name: str
    seats_remaining: int
