import logging
import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.equipment.models import (
    EquipmentRequestLine,
    EquipmentReservation,
)
from app.event import change_request_service as organiser_rules
from app.event import edit_service as edit_rules
from app.event.change_decision_schemas import (
    ChangeDecisionOut,
    ChangeRequestReviewOut,
    ChangeReviewOut,
    ImpactOut,
    PersonOut,
)
from app.event.models import (
    AuditAction,
    ChangeRequestStatus,
    Event,
    EventAuditEntry,
    EventChangeRequest,
    EventReviewFlag,
    EventStatus,
    ReviewFlagKind,
)
from app.event.request_schemas import CoordinatorOut, EventRequestOut
from app.event.review_flag_service import flag_out
from app.event.self_decision import refuse_self_decision
from app.notification.service import Notifier
from app.registration.models import ACTIVE_STATUSES, Registration
from app.user.models import User, UserRole
from app.venue.models import LIVE_BOOKING_STATUSES, VenueBooking

logger = logging.getLogger(__name__)

BOOKINGS, RESERVATIONS, REGISTRATIONS = (
    ReviewFlagKind.VENUE_BOOKING,
    ReviewFlagKind.EQUIPMENT_RESERVATION,
    ReviewFlagKind.REGISTRATIONS,
)
SCHEDULE_KINDS = (BOOKINGS, RESERVATIONS, REGISTRATIONS)
# DECISION-PENDING: D103 — the significant fields (the schedule, attendance, layout, venue and equipment), and,
# DECISION-PENDING: D104 — which arrangements each one flags. Name, category, purpose and join link aren't significant.
SIGNIFICANT_FIELDS: dict[str, tuple[ReviewFlagKind, ...]] = {
    "start_at": SCHEDULE_KINDS,
    "end_at": SCHEDULE_KINDS,
    "preferred_dates": SCHEDULE_KINDS,
    "preferred_start_time": SCHEDULE_KINDS,
    "preferred_end_time": SCHEDULE_KINDS,
    "expected_attendees": (BOOKINGS, REGISTRATIONS),
    "capacity": (BOOKINGS, REGISTRATIONS),
    "room_layout_preference": (BOOKINGS,),
    "accessibility_needs": (BOOKINGS,),
    "delivery_mode": (BOOKINGS, REGISTRATIONS),
    "equipment_needs": (RESERVATIONS,),
}
# DECISION-PENDING: D105 — flags, Planning and the safety approval apply once the event is being arranged; at the
# request stage a significant change just takes its values. Approving is refused once the event is past changing.
ARRANGED_STATUSES = (EventStatus.APPROVED, EventStatus.PLANNING, EventStatus.CONFIRMED)
NOT_APPROVABLE = (EventStatus.PREPARATION, EventStatus.CANCELLED, EventStatus.COMPLETED, EventStatus.REJECTED)
# US12 edits are made in Planning (EVENT_NOT_EDITABLE), and may still apply once the event is Confirmed.
EDIT_STAGES = (EventStatus.PLANNING, EventStatus.CONFIRMED)
LABELS = organiser_rules.LABELS | edit_rules.LABELS
REASON_MAX_LENGTH = 1000  # as US17's and US29a's


def _lock_event(db: Session, event_id: uuid.UUID) -> Event:
    """FOR UPDATE, first, as US12's edit, US18's confirm and US9's cancel do: a second decision, an edit or a
    status change waits here and then sees the first. Module level so the race tests can hold it at a barrier."""
    return db.scalars(
        select(Event).where(Event.id == event_id).with_for_update().execution_options(populate_existing=True)
    ).one()


def _source(request: EventChangeRequest, event: Event) -> str:
    # DECISION-PENDING: D102 — the event's creator asked (US29a), or a coordinator saved a critical edit (US12).
    return "organiser" if request.requested_by_user_id == event.created_by_user_id else "coordinator"


def _decides(user: User, request: EventChangeRequest, event: Event, acting_as: UserRole | None = None) -> bool:
    """D102: the assigned coordinator decides what they didn't make; a Lead decides the coordinator's own edit.
    `acting_as` keeps to one of the two for a user holding both (the list's Role switcher); None is either."""
    if (
        acting_as in (None, UserRole.COORDINATOR)
        and user.holds(UserRole.COORDINATOR)
        and event.coordinator_id == user.id
        and request.requested_by_user_id != user.id
    ):
        return True
    return (
        acting_as in (None, UserRole.COORDINATOR_LEAD)
        and user.holds(UserRole.COORDINATOR_LEAD)
        and _source(request, event) == "coordinator"
        and request.requested_by_user_id == event.coordinator_id
        and request.requested_by_user_id != user.id
    )


def _own(user: User, request: EventChangeRequest, event: Event) -> bool:
    """Their own request on an event they work on: reachable, so refused as a self-decision rather than hidden."""
    return request.requested_by_user_id == user.id and (event.coordinator_id == user.id or user.holds(UserRole.COORDINATOR_LEAD))


def _normal(field: str, value: Any) -> Any:
    """A value in a form two can be compared in (D107): instants as instants (the seed writes +08:00 and the
    database returns UTC), dates and times parsed, lists kept in their order."""
    if value is None or value == "" or value == []:
        return None
    try:
        if field in ("start_at", "end_at"):
            return datetime.fromisoformat(value) if isinstance(value, str) else value
        if field == "preferred_dates":
            return [date.fromisoformat(item) if isinstance(item, str) else item for item in value]
        if field in ("preferred_start_time", "preferred_end_time"):
            return time.fromisoformat(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return value
    return value


def _current(event: Event, field: str) -> Any:
    return organiser_rules._json(getattr(event, field))


def _significant(request: EventChangeRequest) -> list[str]:
    return [change["field"] for change in request.changes if change["field"] in SIGNIFICANT_FIELDS]


def _kinds(fields: list[str]) -> dict[ReviewFlagKind, list[str]]:
    """Each arrangement kind the significant fields touch, with those fields in the request's order."""
    kinds: dict[ReviewFlagKind, list[str]] = {}
    for field in fields:
        for kind in SIGNIFICANT_FIELDS[field]:
            kinds.setdefault(kind, []).append(field)
    return kinds


def _live_bookings(db: Session, event_id: uuid.UUID, lock: bool = False) -> list[VenueBooking]:
    query = (
        select(VenueBooking)
        .where(VenueBooking.event_id == event_id, VenueBooking.status.in_(LIVE_BOOKING_STATUSES))
        .order_by(VenueBooking.starts_at, VenueBooking.reference)
    )
    # The bookings after the event, as US18's confirm locks them (§1a's lock order).
    return db.scalars(query.with_for_update() if lock else query).all()


def _reserved_lines(db: Session, event_id: uuid.UUID) -> list[EquipmentRequestLine]:
    return db.scalars(
        select(EquipmentRequestLine)
        .join(EquipmentReservation, EquipmentReservation.request_line_id == EquipmentRequestLine.id)
        .where(EquipmentRequestLine.event_id == event_id)
        .order_by(EquipmentRequestLine.created_at, EquipmentRequestLine.id)
    ).all()


def _active_registrations(db: Session, event_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(Registration).where(Registration.event_id == event_id, Registration.status.in_(ACTIVE_STATUSES))
    )


def _person(user: User) -> PersonOut:
    return PersonOut.model_validate(user)


class ChangeDecisionService:
    """US29b (SCRUM-142, story SCRUM-98): the coordinator, or a Lead for a coordinator's own US12 edit, reviews a
    pending change request and approves or rejects it (AC 1, 2). Approving a significant change on an event being
    arranged moves a Confirmed event back to Planning, flags the arrangements it may have overtaken and clears the
    safety approval (AC 3, 6). The decision and what it changed go in the event's History (AC 5), and the
    requester is told after the commit (AC 4)."""

    # --- reading ---

    def list_for(
        self,
        db: Session,
        user: User,
        status: str = "pending_approval",
        event_id: uuid.UUID | None = None,
        acting_as: UserRole | None = None,
    ) -> list[ChangeRequestReviewOut]:
        query = select(EventChangeRequest, Event).join(Event, Event.id == EventChangeRequest.event_id)
        if status == "pending_approval":
            query = query.where(EventChangeRequest.status == ChangeRequestStatus.PENDING_APPROVAL)
        elif status == "decided":
            query = query.where(EventChangeRequest.status != ChangeRequestStatus.PENDING_APPROVAL)
        if event_id is not None:
            query = query.where(Event.id == event_id)
        rows = db.execute(query.order_by(EventChangeRequest.created_at, EventChangeRequest.id)).all()
        return [self._out(db, request, event) for request, event in rows if _decides(user, request, event, acting_as)]

    def get(self, db: Session, user: User, request_id: uuid.UUID) -> ChangeRequestReviewOut:
        request, event = self._reachable(db, user, request_id)
        return self._out(db, request, event)

    # --- deciding ---

    def approve(
        self, db: Session, user: User, request_id: uuid.UUID, now: datetime, notifier: Notifier
    ) -> ChangeDecisionOut:
        request, event = self._lock(db, user, request_id)
        # DECISION-PENDING: D105 — nothing changes an event past the point of changing it; it can still be rejected.
        if event.status in NOT_APPROVABLE:
            raise DomainError(409, "CHANGE_NOT_ALLOWED", status=event.status.value)
        cleaned = self._recheck(request, event, now)

        applied = [(change["field"], _current(event, change["field"]), cleaned[change["field"]]) for change in request.changes]
        for field, _, value in applied:
            setattr(event, field, value)
        for field, previous, value in applied:
            self._entry(db, event, user, request, now, AuditAction.APPLIED, field, previous, organiser_rules._json(value))
        self._entry(db, event, user, request, now, AuditAction.DECIDED, "change_request", "pending_approval", {"decision": "approved"})

        flags: list[EventReviewFlag] = []
        status_change = None
        safety_cleared = False
        significant = _significant(request)
        if significant and event.status in ARRANGED_STATUSES:
            flags = self._flag(db, event, request, significant, now)
            # DECISION-PENDING: D105 — a Confirmed event goes back to Planning and is no longer confirmed.
            if event.status == EventStatus.CONFIRMED:
                self._entry(db, event, user, request, now, AuditAction.STATUS_CHANGED, "status", "confirmed", "planning")
                self._entry(
                    db, event, user, request, now, AuditAction.CONFIRMATION_CLEARED, "confirmation",
                    {"confirmed_at": organiser_rules._json(event.confirmed_at), "confirmed_by": str(event.confirmed_by_user_id)}
                    if event.confirmed_at else None,
                    None,
                )
                event.status = EventStatus.PLANNING
                event.confirmed_at = None
                event.confirmed_by_user_id = None
                status_change = {"from": "confirmed", "to": "planning"}
            # DECISION-PENDING: D106 — the safety approval no longer covers the event; its review row stays.
            if event.safety_approved_at is not None:
                self._entry(
                    db, event, user, request, now, AuditAction.SAFETY_APPROVAL_CLEARED, "safety_approval",
                    {"approved_at": organiser_rules._json(event.safety_approved_at), "approved_by": str(event.safety_approved_by_user_id)},
                    None,
                )
                event.safety_approved_at = None
                event.safety_approved_by_user_id = None
                safety_cleared = True

        request.status = ChangeRequestStatus.APPROVED
        request.decided_at = now
        request.decided_by_user_id = user.id
        result = self._decision_out(db, request, event, status_change, flags, safety_cleared)
        notices = self._notices(db, request, event, "approved", status_change, safety_cleared, flags)
        db.commit()

        self._send(notifier, notices)
        return result

    def reject(
        self, db: Session, user: User, request_id: uuid.UUID, reason: Any, now: datetime, notifier: Notifier
    ) -> ChangeDecisionOut:
        request, event = self._lock(db, user, request_id)
        text = reason.strip() if isinstance(reason, str) else ""
        if not text:
            raise DomainError(422, "MISSING_REQUIRED_FIELD", fields=["reason"])
        if len(text) > REASON_MAX_LENGTH:
            raise DomainError(
                422, "INVALID_CHANGE_DECISION", fields=["reason"],
                errors={"reason": f"The reason must be at most {REASON_MAX_LENGTH} characters."},
            )
        self._entry(
            db, event, user, request, now, AuditAction.DECIDED, "change_request", "pending_approval",
            {"decision": "rejected", "reason": text},
        )
        request.status = ChangeRequestStatus.REJECTED
        request.decided_at = now
        request.decided_by_user_id = user.id
        request.rejection_reason = text
        result = self._decision_out(db, request, event, None, [], False)
        notices = self._notices(db, request, event, "rejected", None, False, [])
        db.commit()

        self._send(notifier, notices)
        return result

    # --- the steps ---

    def _reachable(self, db: Session, user: User, request_id: uuid.UUID) -> tuple[EventChangeRequest, Event]:
        """404 unless this user decides it (D102); 403 if it's their own (D51), before whether it's still pending."""
        request = db.get(EventChangeRequest, request_id)
        event = db.get(Event, request.event_id) if request else None
        if request is None or event is None:
            raise DomainError(404, "NOT_FOUND")
        if not _decides(user, request, event):
            if _own(user, request, event):
                refuse_self_decision(user, created_by_user_id=request.requested_by_user_id)
            raise DomainError(404, "NOT_FOUND")
        return request, event

    def _lock(self, db: Session, user: User, request_id: uuid.UUID) -> tuple[EventChangeRequest, Event]:
        found, _ = self._reachable(db, user, request_id)
        event = _lock_event(db, found.event_id)
        request = db.scalars(
            select(EventChangeRequest)
            .where(EventChangeRequest.id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        # Calvin's #125 review: who decides (D102), again on the locked rows. A reassignment committed after the
        # first check refuses the old coordinator, as someone else's request would be.
        if not _decides(user, request, event):
            raise DomainError(404, "NOT_FOUND")
        if request.status != ChangeRequestStatus.PENDING_APPROVAL:
            raise DomainError(409, "CHANGE_REQUEST_NOT_PENDING", status=request.status.value)
        return request, event

    def _stale(self, request: EventChangeRequest, event: Event, now: datetime) -> tuple[dict[str, str], dict[str, Any]]:
        """D107: each field's reason it can't be applied as asked, and the cleaned values of the rest."""
        reasons: dict[str, str] = {}
        organiser = _source(request, event) == "organiser"
        allowed = organiser_rules.allowed_fields(event) if organiser else (
            edit_rules.EDIT_FIELDS if event.status in EDIT_STAGES else ()
        )
        for change in request.changes:
            field = change["field"]
            if _normal(field, change["old_value"]) != _normal(field, _current(event, field)):
                reasons[field] = "changed"
            elif field not in allowed:
                reasons[field] = "not_at_this_stage"
        values = {c["field"]: c["new_value"] for c in request.changes if c["field"] not in reasons}
        cleaned: dict[str, Any] = {}
        if values:
            try:
                cleaned = (
                    organiser_rules._clean(values, event, now.date()) if organiser else edit_rules._clean(values, event)
                )
            except DomainError as error:
                for field in error.extra.get("fields", list(values)):
                    reasons.setdefault(field, "invalid")
        return reasons, cleaned

    def _recheck(self, request: EventChangeRequest, event: Event, now: datetime) -> dict[str, Any]:
        reasons, cleaned = self._stale(request, event, now)
        if reasons:
            # DECISION-PENDING: D107 — nothing is applied; the request can still be rejected.
            raise DomainError(
                409,
                "CHANGE_REQUEST_STALE",
                fields=[
                    {
                        "field": c["field"],
                        "reason": reasons[c["field"]],
                        "requested_from": c["old_value"],
                        "current": _current(event, c["field"]),
                        "proposed": c["new_value"],
                    }
                    for c in request.changes
                    if c["field"] in reasons
                ],
                message="The event has changed since this request was made, so it can't be applied as asked. Reject it with a reason.",
            )
        return cleaned

    def _flag(
        self, db: Session, event: Event, request: EventChangeRequest, significant: list[str], now: datetime
    ) -> list[EventReviewFlag]:
        """DECISION-PENDING: D104 — one open flag per affected item; a later change adds its fields to it. Nothing on
        the booking, reservation or registrations changes (AC 3)."""
        kinds = _kinds(significant)
        targets: list[tuple[ReviewFlagKind, dict[str, uuid.UUID]]] = []
        if BOOKINGS in kinds:
            targets += [(BOOKINGS, {"venue_booking_id": b.id}) for b in _live_bookings(db, event.id, lock=True)]
        if RESERVATIONS in kinds:
            targets += [(RESERVATIONS, {"equipment_request_line_id": line.id}) for line in _reserved_lines(db, event.id)]
        if REGISTRATIONS in kinds and _active_registrations(db, event.id):
            targets.append((REGISTRATIONS, {}))
        flags = []
        for kind, target in targets:
            query = select(EventReviewFlag).where(
                EventReviewFlag.event_id == event.id, EventReviewFlag.kind == kind, EventReviewFlag.cleared_at.is_(None)
            )
            for column, value in target.items():
                query = query.where(getattr(EventReviewFlag, column) == value)
            flag = db.scalars(query.with_for_update()).one_or_none()
            if flag is None:
                flag = EventReviewFlag(
                    event_id=event.id, change_request_id=request.id, kind=kind, fields=list(kinds[kind]), raised_at=now, **target
                )
                db.add(flag)
            else:
                flag.fields = [*flag.fields, *[f for f in kinds[kind] if f not in flag.fields]]
            flags.append(flag)
        db.flush()
        return flags

    def _entry(
        self, db: Session, event: Event, user: User, request: EventChangeRequest, now: datetime,
        action: AuditAction, field: str, previous: Any, new: Any,
    ) -> None:
        db.add(
            EventAuditEntry(
                event_id=event.id, user_id=user.id, field_name=field, previous_value=previous, new_value=new,
                change_request_id=request.id, action=action, created_at=now,
            )
        )
        db.flush()

    # --- what goes back ---

    def _impact(self, db: Session, request: EventChangeRequest, event: Event) -> ImpactOut | None:
        if request.status != ChangeRequestStatus.PENDING_APPROVAL:
            return None
        significant = _significant(request)
        if not significant:
            return ImpactOut(
                status_after=event.status.value, venue_bookings=0, equipment_reservations=0, registrations=0,
                safety_review_required=False,
            )
        if event.status not in ARRANGED_STATUSES:
            return ImpactOut(
                status_after=event.status.value, venue_bookings=None, equipment_reservations=None, registrations=None,
                safety_review_required=None,
            )
        kinds = _kinds(significant)
        return ImpactOut(
            status_after=EventStatus.PLANNING.value if event.status == EventStatus.CONFIRMED else event.status.value,
            venue_bookings=len(_live_bookings(db, event.id)) if BOOKINGS in kinds else 0,
            equipment_reservations=len(_reserved_lines(db, event.id)) if RESERVATIONS in kinds else 0,
            registrations=_active_registrations(db, event.id) if REGISTRATIONS in kinds else 0,
            safety_review_required=event.safety_approved_at is not None,
        )

    def _out(self, db: Session, request: EventChangeRequest, event: Event) -> ChangeRequestReviewOut:
        pending = request.status == ChangeRequestStatus.PENDING_APPROVAL
        changes = [
            ChangeReviewOut(
                field=c["field"],
                label=LABELS.get(c["field"], c["field"]),
                old_value=c["old_value"],
                new_value=c["new_value"],
                current_value=_current(event, c["field"]),
                stale=pending and _normal(c["field"], c["old_value"]) != _normal(c["field"], _current(event, c["field"])),
            )
            for c in request.changes
        ]
        decided_by = db.get(User, request.decided_by_user_id) if request.decided_by_user_id else None
        return ChangeRequestReviewOut(
            id=request.id,
            event_id=event.id,
            event_name=event.name,
            request_reference=event.request_reference,
            event_status=event.status.value,
            source=_source(request, event),
            requested_by=_person(db.get(User, request.requested_by_user_id)),
            reason=request.reason,
            status=request.status,
            created_at=request.created_at,
            changes=changes,
            significant=bool(_significant(request)),
            impact=self._impact(db, request, event),
            decided_at=request.decided_at,
            decided_by=CoordinatorOut.model_validate(decided_by) if decided_by else None,
            rejection_reason=request.rejection_reason,
        )

    def _decision_out(
        self, db: Session, request: EventChangeRequest, event: Event, status_change: dict | None,
        flags: list[EventReviewFlag], safety_cleared: bool,
    ) -> ChangeDecisionOut:
        db.flush()
        db.refresh(event, ["coordinator", "decided_by"])
        return ChangeDecisionOut(
            change_request=self._out(db, request, event),
            event=EventRequestOut.model_validate(event),
            status_change=status_change,
            flags=[flag_out(db, flag) for flag in flags],
            safety_review_required=safety_cleared,
        )

    # --- after the commit (AC 4) ---

    def _notices(
        self, db: Session, request: EventChangeRequest, event: Event, decision: str, status_change: dict | None,
        safety_cleared: bool, flags: list[EventReviewFlag],
    ) -> list[tuple[str, dict]]:
        """Gathered before the commit, sent after it. DECISION-PENDING: D102 — the requester hears, and the event's
        organiser too when an approved US12 edit changed their event."""
        name = event.name or event.request_reference or str(event.id)
        common = {
            "event_id": event.id,
            "event_name": name,
            "decision": decision,
            "fields": [c["field"] for c in request.changes],
            "rejection_reason": request.rejection_reason,
            "status_change": status_change["to"] if status_change else None,
            "safety_review_required": safety_cleared,
        }
        notices: list[tuple[str, dict]] = []
        requester = db.get(User, request.requested_by_user_id)
        if requester is not None and requester.is_active:
            notices.append(("change_request_decided", common | {"email": requester.email, "to_requester": True}))
        if decision == "approved" and _source(request, event) == "coordinator" and event.created_by_user_id:
            organiser = db.get(User, event.created_by_user_id)
            if organiser is not None and organiser.is_active and organiser.id != request.requested_by_user_id:
                notices.append(("change_request_decided", common | {"email": organiser.email, "to_requester": False}))
        # DECISION-PENDING: D104 — Venue staff about each flagged booking, Tech support about each reservation.
        staff_for = {BOOKINGS: UserRole.VENUE_STAFF, RESERVATIONS: UserRole.TECH_SUPPORT}
        for flag in flags:
            role = staff_for.get(flag.kind)
            if role is None:
                continue
            out = flag_out(db, flag)
            staff = db.scalars(select(User).where(User.roles.any(role), User.is_active.is_(True)).order_by(User.email)).all()
            for member in staff:
                notices.append((
                    "arrangement_flagged",
                    {"email": member.email, "event_id": event.id, "event_name": name, "kind": flag.kind,
                     "label": out.target.label if out.target else "", "fields": list(flag.fields)},
                ))
        return notices

    def _send(self, notifier: Notifier, notices: list[tuple[str, dict]]) -> None:
        for method, call in notices:
            try:
                getattr(notifier, method)(**call)
            except Exception:
                logger.exception("could not tell %s about change request decision on event %s", call["email"], call["event_id"])


change_decision_service = ChangeDecisionService()
