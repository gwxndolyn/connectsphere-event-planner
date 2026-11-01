import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.equipment.models import EquipmentLineStatus, EquipmentRequestLine, EquipmentType
from app.event.assignment_service import MISSING_NAME, MISSING_REFERENCE
from app.event.confirmation_service import confirmation_service
from app.event.models import Event, EventStatus
from app.event.request_service import event_request_service
from app.event.self_decision import refuse_self_decision
from app.notification.service import Notifier
from app.safety.models import CHECKLIST, CHECKLIST_KEYS, SafetyReview
from app.safety.schemas import (
    ChecklistItemOut,
    ReviewEquipmentOut,
    ReviewEventOut,
    ReviewVenueOut,
    SafetyQueueOut,
    SafetyQueueRowOut,
    SafetyReviewDetailOut,
    SafetyReviewInternalOut,
    SafetyReviewOut,
    SafetyReviewWrite,
    SafetyStatusOut,
)
from app.safety.state import latest_review, safety_state
from app.user.models import User
from app.venue.models import Venue, VenueBooking, VenueBookingStatus

logger = logging.getLogger(__name__)

# AC 1, 3: an event is reviewed before it is confirmed (US18), so while it is Approved or Planning.
REVIEWABLE_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING)
# The statuses a Safety Officer may still open to read what was decided.
READABLE_STATUSES = REVIEWABLE_STATUSES + (EventStatus.CONFIRMED, EventStatus.PREPARATION)


class SafetyService:
    """SCRUM-99 (US30a): the Safety Officer's queue, checklist review and decision, and what the
    Coordinator and Organiser see of it."""

    # --- the Safety Officer ---

    def queue(self, db: Session) -> SafetyQueueOut:
        """AC 1: events whose venue bookings are approved and equipment lines reserved, with no safety
        decision yet (or one sent back after a rejection). Oldest submission first."""
        events = db.scalars(
            select(Event)
            .where(Event.status.in_(REVIEWABLE_STATUSES), Event.safety_approved_at.is_(None))
            .order_by(Event.submitted_at, Event.id)
        ).all()
        rows = []
        for event in events:
            latest = latest_review(db, event.id)
            if safety_state(event, latest) != "pending":
                continue
            ready, approved = self._arrangements(db, event, lock=False)
            if not ready:
                continue
            rows.append(
                SafetyQueueRowOut(
                    event_id=event.id,
                    name=event.name,
                    request_reference=event.request_reference,
                    expected_attendees=event.expected_attendees,
                    venues=list(dict.fromkeys(venue.name for _, venue in approved)),
                    starts_at=min(booking.starts_at for booking, _ in approved),
                    resent=latest is not None,
                )
            )
        return SafetyQueueOut(events=rows)

    def detail(self, db: Session, event_id: uuid.UUID) -> SafetyReviewDetailOut:
        event = db.get(Event, event_id)
        if event is None or event.status not in READABLE_STATUSES:
            raise DomainError(404, "NOT_FOUND")
        latest = latest_review(db, event.id)
        state = safety_state(event, latest)
        ready, approved = self._arrangements(db, event, lock=False)
        # AC 9: an event is only opened because it is in the queue or has been reviewed already.
        if latest is None and not (state == "pending" and ready and event.status in REVIEWABLE_STATUSES):
            raise DomainError(404, "NOT_FOUND")
        history = db.scalars(
            select(SafetyReview)
            .where(SafetyReview.event_id == event.id)
            .order_by(SafetyReview.created_at.desc(), SafetyReview.id)
        ).all()
        lines = db.execute(
            select(EquipmentRequestLine, EquipmentType)
            .join(EquipmentType, EquipmentType.id == EquipmentRequestLine.equipment_type_id)
            .where(
                EquipmentRequestLine.event_id == event.id,
                EquipmentRequestLine.status != EquipmentLineStatus.REJECTED,
            )
            .order_by(EquipmentType.name)
        ).all()
        return SafetyReviewDetailOut(
            event=ReviewEventOut.model_validate(event, from_attributes=True),
            state=state,  # type: ignore[arg-type]
            venues=[
                ReviewVenueOut(
                    booking_reference=booking.reference,
                    venue_name=venue.name,
                    location=venue.location,
                    venue_capacity=venue.capacity,
                    venue_facilities=venue.facilities,
                    venue_accessibility_features=venue.accessibility_features,
                    venue_room_layouts=venue.room_layouts,
                    starts_at=booking.starts_at,
                    ends_at=booking.ends_at,
                    expected_attendees=booking.expected_attendees,
                    room_layout=booking.room_layout,
                    required_facilities=booking.required_facilities,
                    required_accessibility_features=booking.required_accessibility_features,
                    special_requirements=booking.special_requirements,
                )
                for booking, venue in approved
            ],
            equipment=[
                ReviewEquipmentOut(equipment_type=kind.name, quantity=line.quantity, notes=line.notes)
                for line, kind in lines
            ],
            checklist=[ChecklistItemOut(key=key, label=label) for key, label in CHECKLIST],
            history=[SafetyReviewInternalOut.model_validate(review) for review in history],
        )

    def review(
        self,
        db: Session,
        officer: User,
        event_id: uuid.UUID,
        body: SafetyReviewWrite,
        now: datetime,
        notifier: Notifier,
    ) -> SafetyReviewInternalOut:
        event = db.scalars(select(Event).where(Event.id == event_id).with_for_update()).one_or_none()
        if event is None or event.status == EventStatus.DRAFT:
            raise DomainError(404, "NOT_FOUND")
        # D51: no one reviews an event they created or coordinate, whatever roles they hold.
        refuse_self_decision(officer, created_by_user_id=event.created_by_user_id, event=event)
        self._check_reviewable(db, event)
        outcome, checklist, comments, notes, issues = self._validated(body)

        review = SafetyReview(
            event_id=event.id,
            reviewer_id=officer.id,
            outcome=outcome,
            checklist=checklist,
            comments=comments,
            internal_notes=notes,
            created_at=now,
        )
        db.add(review)
        if outcome == "approved":
            # AC 3: what lets the event be confirmed (US18) and then move to Preparation.
            event.safety_approved_at = now
            event.safety_approved_by_user_id = officer.id
        db.flush()
        db.refresh(review, ["reviewer"])
        result = SafetyReviewInternalOut.model_validate(review)
        notice = (event.coordinator_id, event.request_reference, event.name)
        db.commit()

        self._notify(db, notifier, event_id, *notice, outcome, comments, issues)
        return result

    # --- the Coordinator and Organiser ---

    def status(self, db: Session, event_id: uuid.UUID, reader: User) -> SafetyStatusOut:
        """AC 7: the outcome and the comments, never the internal notes. Readable by whoever may read the
        request itself (D11, D48): its Organiser, its assigned coordinator, a Lead."""
        event_request_service.get(db, event_id, reader)  # raises 404 when not readable
        event = db.get(Event, event_id)
        assert event is not None
        reviews = db.scalars(
            select(SafetyReview)
            .where(SafetyReview.event_id == event.id)
            .order_by(SafetyReview.created_at.desc(), SafetyReview.id)
        ).all()
        state = safety_state(event, reviews[0] if reviews else None)
        return SafetyStatusOut(
            state=state,  # type: ignore[arg-type]
            reviews=[SafetyReviewOut.model_validate(review) for review in reviews],
        )

    def request_review(self, db: Session, coordinator: User, event_id: uuid.UUID, now: datetime) -> SafetyStatusOut:
        """AC 4: after a rejection the coordinator revises the arrangement and sends it for another review."""
        event = db.scalars(select(Event).where(Event.id == event_id).with_for_update()).one_or_none()
        if event is None or event.status == EventStatus.DRAFT or event.coordinator_id != coordinator.id:
            raise DomainError(404, "NOT_FOUND")
        if event.status not in REVIEWABLE_STATUSES:
            raise DomainError(409, "SAFETY_REVIEW_NOT_ALLOWED", reason="status", status=event.status.value)
        state = safety_state(event, latest_review(db, event.id))
        if state != "rejected":
            # Approved, never reviewed, or already sent back.
            reason = "already_approved" if state == "approved" else "not_rejected"
            if state == "pending" and latest_review(db, event.id) is not None:
                reason = "already_requested"
            raise DomainError(409, "SAFETY_REVIEW_NOT_ALLOWED", reason=reason, status=event.status.value)
        event.safety_review_requested_at = now
        db.commit()
        return self.status(db, event_id, coordinator)

    # --- rules ---

    def _arrangements(
        self, db: Session, event: Event, *, lock: bool
    ) -> tuple[bool, list[tuple[VenueBooking, Venue]]]:
        """AC 1: the venues arranged (US24's rule, D72) and the requested equipment approved and reserved.
        Technical support is the coordinator's to arrange for confirming, and the safety item is the thing
        being decided, so neither is part of this."""
        readiness, approved = confirmation_service._readiness(db, event, lock=lock)
        return all(item.complete for item in readiness.items if item.kind in ("venue", "equipment")), approved

    def _check_reviewable(self, db: Session, event: Event) -> None:
        if event.status not in REVIEWABLE_STATUSES:
            raise DomainError(409, "SAFETY_REVIEW_NOT_ALLOWED", reason="status", status=event.status.value)
        latest = latest_review(db, event.id)
        state = safety_state(event, latest)
        if state == "approved":
            raise DomainError(409, "SAFETY_REVIEW_NOT_ALLOWED", reason="already_approved", status=event.status.value)
        if state == "rejected":
            # Waiting for the coordinator to revise it and send it back (AC 4).
            raise DomainError(409, "SAFETY_REVIEW_NOT_ALLOWED", reason="awaiting_revision", status=event.status.value)
        ready, _ = self._arrangements(db, event, lock=True)
        if not ready:
            raise DomainError(
                409, "SAFETY_REVIEW_NOT_ALLOWED", reason="arrangements_incomplete", status=event.status.value
            )

    def _validated(self, body: SafetyReviewWrite) -> tuple[str, dict, str | None, str | None, list[str]]:
        """AC 2-4: an outcome, all seven checklist items answered, and comments on a rejection."""
        sent = body.checklist or {}
        unknown = [key for key in sent if key not in CHECKLIST_KEYS]
        if unknown:
            raise DomainError(422, "INVALID_SAFETY_REVIEW", fields=["checklist"], items=unknown)
        comments = (body.comments or "").strip() or None
        missing: list[str] = []
        if body.outcome is None:
            missing.append("outcome")
        missing += [f"checklist.{key}" for key in CHECKLIST_KEYS if sent.get(key) is None or sent[key].result is None]
        if body.outcome == "rejected" and comments is None:
            missing.append("comments")
        if missing:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=missing)
        assert body.outcome is not None

        checklist = {
            key: {"result": sent[key].result, "comment": (sent[key].comment or "").strip() or None}
            for key in CHECKLIST_KEYS
        }
        flagged = [key for key in CHECKLIST_KEYS if checklist[key]["result"] == "issue"]
        if body.outcome == "approved" and flagged:
            # An approval can't leave a flagged concern behind it.
            raise DomainError(422, "CHECKLIST_HAS_ISSUES", fields=[f"checklist.{key}" for key in flagged])
        labels = dict(CHECKLIST)
        return (
            body.outcome,
            checklist,
            comments,
            (body.internal_notes or "").strip() or None,
            [labels[key] for key in flagged],
        )

    def _notify(
        self,
        db: Session,
        notifier: Notifier,
        event_id: uuid.UUID,
        coordinator_id: uuid.UUID | None,
        request_reference: str | None,
        event_name: str | None,
        outcome: str,
        comments: str | None,
        issues: list[str],
    ) -> None:
        """AC 5: the event's coordinator hears the outcome and the comments. After the commit, best effort
        like the other notices: a failure is logged and never undoes the review."""
        try:
            coordinator = db.get(User, coordinator_id) if coordinator_id else None
        except Exception:
            logger.exception("could not look up the coordinator of event %s", event_id)
            return
        if coordinator is None or not coordinator.email:
            logger.warning("could not notify the coordinator of event %s: none assigned or no email", event_id)
            return
        try:
            notifier.safety_review_decided(
                email=coordinator.email,
                request_reference=request_reference or MISSING_REFERENCE,
                event_name=event_name or MISSING_NAME,
                outcome=outcome,  # type: ignore[arg-type]
                comments=comments,
                issues=issues,
            )
        except Exception:
            logger.exception("could not send the safety review notice for event %s", event_id)


safety_service = SafetyService()
