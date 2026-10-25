from app.core.exceptions import DomainError
from app.event.models import Event
from app.user.models import User


# DECISION-PENDING: D51 — no one decides a record they created, whatever roles they hold (US16b,
# decided by the acting PO on 25 Oct). Every decision path calls this, so a new one (expiry, reassignment)
# gets the rule by calling it too; tests/user/test_role_scope.py fails on a decision route that isn't tried.
def refuse_self_decision(decider: User, *, created_by_user_id, event: Event | None = None) -> None:
    """403 SELF_DECISION_NOT_ALLOWED if `decider` created the record, or, when the record belongs to an
    `event` (a venue booking, an equipment line), is that event's current coordinator: they're a party to
    it even when a previous coordinator made the request. Call it before checking whether the record is
    still pending, so the refusal doesn't depend on its state."""
    if created_by_user_id == decider.id or (event is not None and event.coordinator_id == decider.id):
        raise DomainError(403, "SELF_DECISION_NOT_ALLOWED")
