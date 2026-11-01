// US30a (SCRUM-99): the Safety Officer's checklist and what the API returns for a review.
export type ChecklistResult = "satisfactory" | "issue";

export interface ChecklistAnswer {
  result: ChecklistResult;
  comment: string | null;
}

export interface ChecklistItem {
  key: string;
  label: string;
}

export interface SafetyQueueRow {
  event_id: string;
  name: string | null;
  request_reference: string | null;
  expected_attendees: number | null;
  venues: string[];
  starts_at: string | null;
  // Sent back after a rejection, so it has been reviewed before.
  resent: boolean;
}

export interface Reviewer {
  id: string;
  name: string;
}

export interface SafetyReview {
  id: string;
  outcome: "approved" | "rejected";
  checklist: Record<string, ChecklistAnswer>;
  comments: string | null;
  reviewer: Reviewer;
  created_at: string;
}

// The Safety Officer's own copy of a review also holds their internal notes.
export interface SafetyReviewInternal extends SafetyReview {
  internal_notes: string | null;
}

export interface ReviewVenue {
  booking_reference: string;
  venue_name: string;
  location: string;
  venue_capacity: number;
  venue_facilities: string[];
  venue_accessibility_features: string[];
  venue_room_layouts: string[];
  starts_at: string;
  ends_at: string;
  expected_attendees: number;
  room_layout: string;
  required_facilities: string[];
  required_accessibility_features: string[];
  special_requirements: string | null;
}

export interface ReviewEquipment {
  equipment_type: string;
  quantity: number;
  notes: string | null;
}

export type SafetyState = "pending" | "approved" | "rejected";

export interface SafetyReviewDetail {
  event: {
    id: string;
    name: string | null;
    request_reference: string | null;
    status: string;
    expected_attendees: number | null;
    room_layout_preference: string | null;
    accessibility_needs: string | null;
    equipment_needs: string | null;
  };
  state: SafetyState;
  venues: ReviewVenue[];
  equipment: ReviewEquipment[];
  checklist: ChecklistItem[];
  history: SafetyReviewInternal[];
}

// What the Organiser and Coordinator read of an event's safety review (no internal notes).
export interface SafetyStatus {
  state: SafetyState;
  reviews: SafetyReview[];
}
