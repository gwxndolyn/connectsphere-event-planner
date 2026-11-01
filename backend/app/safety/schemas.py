import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.event.request_schemas import CoordinatorOut


class ChecklistEntryWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional here so a missing result is the API's own MISSING_REQUIRED_FIELD, not FastAPI's generic 422.
    result: Literal["satisfactory", "issue"] | None = None
    comment: str | None = Field(default=None, max_length=1000)


class SafetyReviewWrite(BaseModel):
    """US30a AC 2-4. Every field is optional here so a missing one gets the API's own
    MISSING_REQUIRED_FIELD, like a blank one (as US17's reject body does)."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["approved", "rejected"] | None = None
    checklist: dict[str, ChecklistEntryWrite] | None = None
    # What the Coordinator and Organiser read; required on a rejection (AC 4).
    comments: str | None = Field(default=None, max_length=2000)
    # The Safety Officer's own notes: never shown to the Organiser or the Coordinator (AC 7).
    internal_notes: str | None = Field(default=None, max_length=2000)


class SafetyReviewOut(BaseModel):
    """A review as the Coordinator and Organiser read it: the outcome and the comments, no internal notes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    outcome: str
    checklist: dict[str, Any]
    comments: str | None
    reviewer: CoordinatorOut
    created_at: datetime


class SafetyReviewInternalOut(SafetyReviewOut):
    """The same review for the Safety Officer, with their internal notes."""

    internal_notes: str | None


class SafetyStatusOut(BaseModel):
    """What the Organiser and Coordinator see of an event's safety review (AC 7)."""

    state: Literal["pending", "approved", "rejected"]
    # Newest first.
    reviews: list[SafetyReviewOut]


class SafetyQueueRowOut(BaseModel):
    event_id: uuid.UUID
    name: str | None
    request_reference: str | None
    expected_attendees: int | None
    venues: list[str]
    starts_at: datetime | None
    # Sent back after a rejection (AC 4), so the Safety Officer knows it has been reviewed before.
    resent: bool


class SafetyQueueOut(BaseModel):
    events: list[SafetyQueueRowOut]


class ReviewEventOut(BaseModel):
    """Only what a safety review needs of the event (AC 9): no organiser, dates of submission or other details."""

    id: uuid.UUID
    name: str | None
    request_reference: str | None
    status: str
    expected_attendees: int | None
    room_layout_preference: str | None
    accessibility_needs: str | None
    equipment_needs: str | None


class ReviewVenueOut(BaseModel):
    booking_reference: str
    venue_name: str
    location: str
    venue_capacity: int
    venue_facilities: list[str]
    venue_accessibility_features: list[str]
    venue_room_layouts: list[str]
    starts_at: datetime
    ends_at: datetime
    expected_attendees: int
    room_layout: str
    required_facilities: list[str]
    required_accessibility_features: list[str]
    special_requirements: str | None


class ReviewEquipmentOut(BaseModel):
    equipment_type: str
    quantity: int
    notes: str | None


class ChecklistItemOut(BaseModel):
    key: str
    label: str


class SafetyReviewDetailOut(BaseModel):
    """What the Safety Officer opens to review (AC 2, 9). `history` is the event's earlier reviews: the
    change history that matters here (deviation 62: there is no change log of attendance, venue, access
    or equipment edits yet)."""

    event: ReviewEventOut
    state: Literal["pending", "approved", "rejected"]
    venues: list[ReviewVenueOut]
    equipment: list[ReviewEquipmentOut]
    checklist: list[ChecklistItemOut]
    history: list[SafetyReviewInternalOut]
