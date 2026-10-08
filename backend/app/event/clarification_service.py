import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.clarification_schemas import ClarificationOut, ClarificationRequestWrite
from app.event.models import (
    CLARIFICATION_SECTIONS,
    ClarificationKind,
    Event,
    EventRequestClarification,
)
from app.user.models import User


class ClarificationService:
    """Storage for an event request's clarification thread (SCRUM-54).

    Deliberately no status checks and no commit: the caller (the SCRUM-53 endpoint) locks the
    event, guards its status, calls `add_request`, moves the event to awaiting_clarification and
    commits, so the message and the status change land in one transaction.
    """

    def add_request(
        self,
        db: Session,
        event: Event,
        coordinator: User,
        body: ClarificationRequestWrite,
        now: datetime,
    ) -> ClarificationOut:
        sections, comment = self._validate_request(body)
        last_round = db.scalar(
            select(func.max(EventRequestClarification.round)).where(
                EventRequestClarification.event_id == event.id,
                EventRequestClarification.kind == ClarificationKind.REQUEST,
            )
        )
        clarification = EventRequestClarification(
            event_id=event.id,
            round=(last_round or 0) + 1,
            kind=ClarificationKind.REQUEST,
            sections=sections,
            comment=comment,
            author_user_id=coordinator.id,
            created_at=now,
        )
        db.add(clarification)
        db.flush()
        return ClarificationOut.model_validate(clarification)

    def list_thread(self, db: Session, event_id: uuid.UUID) -> list[ClarificationOut]:
        """Every message, oldest round first, each question before its reply."""
        clarifications = db.scalars(
            select(EventRequestClarification)
            .where(EventRequestClarification.event_id == event_id)
            .order_by(EventRequestClarification.round, EventRequestClarification.kind)
        ).all()
        return [ClarificationOut.model_validate(clarification) for clarification in clarifications]

    def _validate_request(self, body: ClarificationRequestWrite) -> tuple[list[str], str]:
        comment = body.comment.strip()
        missing = [name for name, value in (("sections", body.sections), ("comment", comment)) if not value]
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)

        unknown = [section for section in body.sections if section not in CLARIFICATION_SECTIONS]
        if unknown or len(set(body.sections)) != len(body.sections):
            raise DomainError(422, "INVALID_CLARIFICATION", fields=["sections"], sections=unknown)

        # Stored in the canonical order, so the thread reads the same however the UI sent them.
        return sorted(body.sections, key=CLARIFICATION_SECTIONS.index), comment


clarification_service = ClarificationService()
