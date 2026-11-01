import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.agenda.schemas import SessionOut, SessionsOut, SessionWrite
from app.agenda.service import agenda_service
from app.core.database import get_db
from app.user.dependencies import require_user_roles
from app.user.models import User, UserRole

# US15 (SCRUM-139): an event's agenda hangs off the event request; a session is edited by its own id.
requests_router = APIRouter(prefix="/api/v1/event-requests", tags=["agenda"])
router = APIRouter(prefix="/api/v1/event-sessions", tags=["agenda"])

Organiser = Annotated[User, Depends(require_user_roles(UserRole.ORGANISER))]
# Who may open a request at all; which requests each may open is the request service's (D47, D48).
Reader = Annotated[
    User, Depends(require_user_roles(UserRole.ORGANISER, UserRole.COORDINATOR, UserRole.COORDINATOR_LEAD))
]


@requests_router.get("/{request_id}/sessions", response_model=SessionsOut)
def list_sessions(request_id: uuid.UUID, reader: Reader, db: Session = Depends(get_db)) -> SessionsOut:
    return agenda_service.list(db, reader, request_id)


@requests_router.post("/{request_id}/sessions", status_code=201, response_model=SessionOut)
def add_session(
    request_id: uuid.UUID, body: SessionWrite, organiser: Organiser, db: Session = Depends(get_db)
) -> SessionOut:
    return agenda_service.add(db, organiser, request_id, body)


@router.patch("/{session_id}", response_model=SessionOut)
def edit_session(
    session_id: uuid.UUID, body: SessionWrite, organiser: Organiser, db: Session = Depends(get_db)
) -> SessionOut:
    return agenda_service.edit(db, organiser, session_id, body)


@router.delete("/{session_id}", status_code=204, response_class=Response)
def delete_session(session_id: uuid.UUID, organiser: Organiser, db: Session = Depends(get_db)) -> None:
    agenda_service.delete(db, organiser, session_id)
