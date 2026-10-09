import logging
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.clarification_schemas import (
    ClarificationOut,
    ClarificationRequestWrite,
    ClarificationResponseWrite,
    ClarificationSentOut,
)
from app.event.models import (
    CLARIFICATION_SECTIONS,
    ClarificationKind,
    Event,
    EventRequestClarification,
    EventStatus,
)
from app.event.request_service import SUBMITTED_REQUEST_STATUSES, event_request_service
from app.notification.service import Notifier
from app.user.models import User

logger = logging.getLogger(__name__)

# DECISION-PENDING: D15 — SCRUM-11 AC 2 (ask from submitted/under_review) and SCRUM-75 AC 1/2
# (more rounds, none once decided). A new round is max(round) + 1, with no limit. A request
# awaiting clarification can't take another question: the organiser's reply answers the latest
# open round, so a second open question would never get its own answer. Approved and rejected
# are 409 too; statuses past the request stage are already 404 (D11).
CLARIFIABLE_STATUSES = (EventStatus.SUBMITTED, EventStatus.UNDER_REVIEW)


class ClarificationService:
    """An event request's clarification thread (US8).

    `send_request` is the whole SCRUM-53 transition and `send_response` the SCRUM-77 one.
    `add_request` is the storage underneath (SCRUM-54): no status checks and no commit, so the
    message and the status change land in one transaction.
    """

    def send_request(
        self,
        db: Session,
        request_id: uuid.UUID,
        coordinator: User,
        body: ClarificationRequestWrite,
        now: datetime,
        notifier: Notifier,
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
        organiser_id = event.created_by_user_id
        request_reference = event.request_reference
        event_name = event.name
        db.commit()

        try:
            if organiser_id is None:
                logger.warning(
                    "could not notify organiser about clarification for request %s: no owner",
                    request_id,
                )
                return result

            organiser = db.get(User, organiser_id)
            if organiser is None or not organiser.email:
                logger.warning(
                    "could not notify organiser about clarification for request %s: no email",
                    request_id,
                )
                return result

            if not request_reference or not event_name:
                logger.warning(
                    "could not notify organiser about clarification for request %s: missing request details",
                    request_id,
                )
                return result

            notifier.clarification_requested(
                email=organiser.email,
                request_reference=request_reference,
                event_name=event_name,
                round=clarification.round,
                sections=clarification.sections,
                comment=clarification.comment,
            )
        except Exception:
            logger.exception(
                "could not notify organiser about clarification for request %s", request_id
            )
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

    def send_response(
        self,
        db: Session,
        request_id: uuid.UUID,
        organiser: User,
        body: ClarificationResponseWrite,
        now: datetime,
    ) -> ClarificationSentOut:
        """The owner answers the open round (US8c AC 1) and the request returns to review (AC 2)."""
        event = db.scalars(
            select(Event).where(Event.id == request_id).with_for_update()
        ).one_or_none()
        # Another organiser's request is a 404, never a 403 (§1a rules).
        if event is None or event.created_by_user_id != organiser.id:
            raise DomainError(404, "NOT_FOUND")
        if event.status != EventStatus.AWAITING_CLARIFICATION:
            raise DomainError(409, "NO_OPEN_CLARIFICATION", status=event.status.value)
        comment = body.comment.strip()
        if not comment:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=["comment"])

        # Awaiting clarification means the latest round has a question and no reply yet; the
        # (event_id, round, kind) unique constraint backs that up.
        open_round = db.scalar(
            select(func.max(EventRequestClarification.round)).where(
                EventRequestClarification.event_id == event.id,
                EventRequestClarification.kind == ClarificationKind.REQUEST,
            )
        )
        if open_round is None:
            raise RuntimeError(f"event request {event.id} awaits clarification but has no question")
        response = EventRequestClarification(
            event_id=event.id,
            round=open_round,
            kind=ClarificationKind.RESPONSE,
            sections=None,
            comment=comment,
            author_user_id=organiser.id,
            created_at=now,
        )
        db.add(response)
        event.status = EventStatus.UNDER_REVIEW
        db.flush()
        result = ClarificationSentOut(clarification=ClarificationOut.model_validate(response), status=event.status)
        db.commit()
        return result

    def read_thread(self, db: Session, request_id: uuid.UUID, reader: User) -> list[ClarificationOut]:
        """The thread for anyone who may read the request itself: owner, or staff per D11."""
        event_request_service.get(db, request_id, reader)  # raises 404 when not readable
        return self.list_thread(db, request_id)

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
