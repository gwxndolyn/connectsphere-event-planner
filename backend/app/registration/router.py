import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.database import get_db
from app.registration.schemas import WithdrawResponse
from app.registration.service import registration_service
from app.user.dependencies import get_current_attendee
from app.user.models import Attendee

router = APIRouter(prefix="/api/v1/registrations", tags=["registrations"])


@router.post("/{registration_id}/withdraw")
def withdraw(
    registration_id: uuid.UUID,
    attendee: Attendee = Depends(get_current_attendee),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
) -> WithdrawResponse:
    return registration_service.withdraw(db, registration_id, attendee, now)
