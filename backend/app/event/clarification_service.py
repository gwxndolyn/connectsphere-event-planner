import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.clarification_schemas import (
    ClarificationOut,
    ClarificationRequestWrite,
    ClarificationSentOut,
)
from app.event.models import (
    CLARIFICATION_SECTIONS,
    ClarificationKind,
    Event,
    EventRequestClarification,
    EventStatus,
)
from app.event.request_service import SUBMITTED_REQUEST_STATUSES
from app.user.models import User

# SCRUM-11 AC 2. Later rounds (8d, SCRUM-56) also start from under_review, once the
# organiser's reply (SCRUM-77) has moved the request back there.
CLARIFIABLE_STATUSES = (EventStatus.SUBMITTED, EventStatus.UNDER_REVIEW)


class ClarificationService:
    """An event request's clarification thread (US8).

    `send_request` is the whole SCRUM-53 transition. `add_request` is the storage underneath it
    (SCRUM-54): no status checks and no commit, so the message and the status change land in
    one transaction.
    """

    def send_request(
        self,
        db: Session,
        request_id: uuid.UUID,
        coordinator: User,
        body: ClarificationRequestWrite,
        now: datetime,
    ) -> ClarificationSentOut:
        event = db.scalars(
            select(Event).where(Event.id == request_id).with_for_update()
        ).one_or_none()
        # Drafts and finished events are invisible to coordinators (D11), so they 404, not 409.
        if event is None or event.status not in SUBMITTED_REQUEST_STATUSES:
            raise DomainError(404, "NOT_FOUND")
        if event.status not in CLARIFIABLE_STATUSES:
            raise DomainError(409, "CLARIFICATION_NOT_ALLOWED", status=event.status.value)

        clarification = self.add_request(db, event, coordinator, body, now)
        event.status = EventStatus.AWAITING_CLARIFICATION
        db.flush()
        result = ClarificationSentOut(clarification=clarification, status=event.status)
        db.commit()
        return result

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
