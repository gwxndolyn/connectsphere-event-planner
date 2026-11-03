import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.event.models import ChangeRequestStatus
from app.event.request_schemas import CoordinatorOut, EventRequestOut


class PersonOut(CoordinatorOut):
    """Who asked: name and email, so the decider can reach them."""

    email: str


class ChangeReviewOut(BaseModel):
    """One field of a change request as the decider reviews it (AC 1): what it was when asked, what is asked
    for, and what it is now. `stale` when the event has moved on since (D107)."""

    field: str
    label: str
    old_value: Any
    new_value: Any
    current_value: Any
    stale: bool


class ImpactOut(BaseModel):
    """What approving a pending request would do (D103 to D106). At the request stage a significant change only
    takes its values, so everything but `status_after` is null there."""

    status_after: str
    venue_bookings: int | None
    equipment_reservations: int | None
    registrations: int | None
    safety_review_required: bool | None


class ChangeRequestReviewOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_name: str | None
    request_reference: str | None
    event_status: str
    # D102: an Organiser's request (US29a) or a coordinator's own US12 edit, told apart by
    # whether the requester created the event.
    source: Literal["organiser", "coordinator"]
    requested_by: PersonOut
    reason: str | None
    status: ChangeRequestStatus
    created_at: datetime
    changes: list[ChangeReviewOut]
    significant: bool
    impact: ImpactOut | None
    decided_at: datetime | None
    decided_by: CoordinatorOut | None
    rejection_reason: str | None


class ChangeRequestReviewsOut(BaseModel):
    change_requests: list[ChangeRequestReviewOut]


class RejectionWrite(BaseModel):
    """Read unchecked, so a missing, blank or over-long reason names its field (AC 2)."""

    model_config = ConfigDict(extra="forbid")

    reason: Any = None


class FlagTargetOut(BaseModel):
    id: uuid.UUID
    label: str
    status: str


class ReviewFlagOut(BaseModel):
    """An arrangement a significant change may have overtaken (AC 3, D104). `resolved` when its booking is no
    longer live or its reservation was released, which counts as reviewed; `open` while neither cleared nor
    resolved."""

    id: uuid.UUID
    event_id: uuid.UUID
    kind: Literal["venue_booking", "equipment_reservation", "registrations"]
    # Null for registrations: the flag is the event's, not one registrant's.
    target: FlagTargetOut | None
    fields: list[str]
    change_request_id: uuid.UUID
    raised_at: datetime
    cleared_at: datetime | None
    cleared_by: CoordinatorOut | None
    cleared_note: str | None
    resolved: bool
    open: bool


class ReviewFlagsOut(BaseModel):
    flags: list[ReviewFlagOut]


class ClearFlagWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Any = None


class ChangeDecisionOut(BaseModel):
    change_request: ChangeRequestReviewOut
    event: EventRequestOut
    # {"from": "confirmed", "to": "planning"} when a significant change moved the event back (D105); else null.
    status_change: dict[str, str] | None
    flags: list[ReviewFlagOut]
    safety_review_required: bool
