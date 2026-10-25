import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.event.assignment_service import MISSING_NAME, MISSING_REFERENCE
from app.event.models import Event, EventStatus
from app.event.request_schemas import EventRequestOut, RequestRejectWrite
from app.notification.service import Notifier, RequestDecision
from app.user.models import User

logger = logging.getLogger(__name__)


class RequestDecisionService:
    """SCRUM-84 (US17): the assigned coordinator approves or rejects a request under review."""

    def approve(
        self, db: Session, coordinator: User, request_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> EventRequestOut:
        event = self._lock_decidable(db, request_id, coordinator)
        return self._decide(db, notifier, coordinator, event, EventStatus.APPROVED, None, now)

    def reject(
        self,
        db: Session,
        coordinator: User,
        request_id: uuid.UUID,
        body: RequestRejectWrite,
        now: datetime,
        notifier: Notifier,
    ) -> EventRequestOut:
        """AC 3: a rejection must say why, and the reason is stored with the request."""
        reason = (body.reason or "").strip()
        event = self._lock_assigned(db, request_id, coordinator)
        if not reason:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=["reason"])
        self._check_decidable(event)
        return self._decide(db, notifier, coordinator, event, EventStatus.REJECTED, reason, now)

    def _lock_decidable(self, db: Session, request_id: uuid.UUID, coordinator: User) -> Event:
        event = self._lock_assigned(db, request_id, coordinator)
        self._check_decidable(event)
        return event

    def _lock_assigned(self, db: Session, request_id: uuid.UUID, coordinator: User) -> Event:
        """The request, locked FOR UPDATE so two decisions, or a decision and a clarification, can't
        both land. The access checks come before the status check, so a refusal doesn't depend on the
        request's state."""
        event = db.scalars(select(Event).where(Event.id == request_id).with_for_update()).one_or_none()
        # AC 1 and D48: only the request's assigned coordinator. Anyone else's, an unassigned request,
        # a draft or an unknown id is 404, never 403, as for other people's records (§1a).
        if event is None or event.status == EventStatus.DRAFT or event.coordinator_id != coordinator.id:
            raise DomainError(404, "NOT_FOUND")
        # D51: no one decides a request they created, whatever roles they hold.
        if event.created_by_user_id == coordinator.id:
            raise DomainError(403, "SELF_DECISION_NOT_ALLOWED")
        return event

    def _check_decidable(self, event: Event) -> None:
        # AC 1, 6: only Under Review. Awaiting Clarification waits for the organiser's answer; Approved,
        # Rejected and Cancelled are already decided; the request is left unchanged.
        if event.status != EventStatus.UNDER_REVIEW:
            raise DomainError(409, "REQUEST_NOT_DECIDABLE", status=event.status.value)

    def _decide(
        self,
        db: Session,
        notifier: Notifier,
        coordinator: User,
        event: Event,
        status: EventStatus,
        reason: str | None,
        now: datetime,
    ) -> EventRequestOut:
        # Set with the status in one flush: a reason on a request that isn't rejected breaks
        # events_rejection_reason_only_when_rejected.
        event.status = status
        event.rejection_reason = reason
        event.decided_at = now
        event.decided_by_user_id = coordinator.id
        db.flush()
        db.refresh(event, ["decided_by"])
        result = EventRequestOut.model_validate(event)
        decision: RequestDecision = "approved" if status == EventStatus.APPROVED else "rejected"
        notice = (event.id, event.created_by_user_id, event.request_reference, event.name)
        db.commit()

        self._notify(db, notifier, *notice, decision, reason)
        return result

    def _notify(
        self,
        db: Session,
        notifier: Notifier,
        request_id: uuid.UUID,
        organiser_id: uuid.UUID | None,
        request_reference: str | None,
        event_name: str | None,
        decision: RequestDecision,
        reason: str | None,
    ) -> None:
        """AC 4: the organiser hears the outcome, with the reason for a rejection. Sent only after the
        decision commits, so a refused one tells no one. Best effort like the other notices: a failure
        is logged and never undoes the decision."""
        try:
            organiser = db.get(User, organiser_id) if organiser_id else None
        except Exception:
            logger.exception("could not look up the organiser of request %s", request_id)
            return
        if organiser is None or not organiser.email:
            logger.warning("could not notify the organiser of request %s: no owner or email", request_id)
            return
        try:
            notifier.request_decided(
                email=organiser.email,
                request_reference=request_reference or MISSING_REFERENCE,
                event_name=event_name or MISSING_NAME,
                decision=decision,
                reason=reason,
            )
        except Exception:
            logger.exception("could not send the decision notice for request %s", request_id)


request_decision_service = RequestDecisionService()
