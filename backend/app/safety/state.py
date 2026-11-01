import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.event.models import Event
from app.safety.models import SafetyReview


def latest_review(db: Session, event_id: uuid.UUID) -> SafetyReview | None:
    return db.scalars(
        select(SafetyReview)
        .where(SafetyReview.event_id == event_id)
        .order_by(SafetyReview.created_at.desc(), SafetyReview.id)
        .limit(1)
    ).first()


# The outcomes after which the coordinator revises the arrangement and sends it back (US30a AC 4, US30b AC 4).
AWAITING_REVISION = ("rejected", "changes_requested")


def resent_for_review(event: Event, latest: SafetyReview | None) -> bool:
    """An arrangement the coordinator has sent back since its rejection, or since changes were requested
    (US30a AC 4, US30b AC 4). The request can only be made after the review exists, so the same instant
    counts as after."""
    return (
        latest is not None
        and latest.outcome in AWAITING_REVISION
        and event.safety_review_requested_at is not None
        and event.safety_review_requested_at >= latest.created_at
    )


def safety_state(event: Event, latest: SafetyReview | None) -> str:
    """`approved`, `rejected` or `changes_requested` (waiting for the coordinator to revise and send it
    back) or `pending` (not reviewed yet, or sent back for another review)."""
    if event.safety_approved_at is not None:
        return "approved"
    if latest is not None and latest.outcome in AWAITING_REVISION and not resent_for_review(event, latest):
        return latest.outcome
    return "pending"
