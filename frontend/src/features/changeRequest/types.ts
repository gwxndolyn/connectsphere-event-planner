import type { EventRequest } from "../eventRequest/types";

// Shapes from backend/app/event/change_request_schemas.py (US29a, SCRUM-97).
export interface FieldChange {
  field: string;
  old_value: unknown;
  new_value: unknown;
}

export interface OrganiserChangeRequest {
  id: string;
  event_id: string;
  event_name: string | null;
  request_reference: string | null;
  // AC 4's "Pending" is pending_approval; US29b decides the others.
  status: "pending_approval" | "approved" | "rejected";
  reason: string | null;
  changes: FieldChange[];
  created_at: string;
  // US29b (SCRUM-142) AC 4: when it was decided, and why a rejection.
  decided_at?: string | null;
  rejection_reason?: string | null;
}

// Shapes from backend/app/event/change_decision_schemas.py (US29b, SCRUM-142).
export interface ChangeReview extends FieldChange {
  label: string;
  current_value: unknown;
  // The event has moved on since the request was made (D107).
  stale: boolean;
}

export interface ChangeImpact {
  status_after: string;
  // Null at the request stage, where a significant change only takes its values (D105).
  venue_bookings: number | null;
  equipment_reservations: number | null;
  registrations: number | null;
  safety_review_required: boolean | null;
}

export interface ChangeRequestReview {
  id: string;
  event_id: string;
  event_name: string | null;
  request_reference: string | null;
  event_status: string;
  source: "organiser" | "coordinator";
  requested_by: { id: string; name: string; email: string };
  reason: string | null;
  status: OrganiserChangeRequest["status"];
  created_at: string;
  changes: ChangeReview[];
  significant: boolean;
  impact: ChangeImpact | null;
  decided_at: string | null;
  decided_by: { id: string; name: string } | null;
  rejection_reason: string | null;
}

export interface ReviewFlag {
  id: string;
  event_id: string;
  kind: "venue_booking" | "equipment_reservation" | "registrations";
  target: { id: string; label: string; status: string } | null;
  fields: string[];
  change_request_id: string;
  raised_at: string;
  cleared_at: string | null;
  cleared_by: { id: string; name: string } | null;
  cleared_note: string | null;
  // Its booking is no longer live, or its reservation was released (D104): nothing left to review.
  resolved: boolean;
  open: boolean;
}

export interface ChangeDecision {
  change_request: ChangeRequestReview;
  event: EventRequest;
  status_change: { from: string; to: string } | null;
  flags: ReviewFlag[];
  safety_review_required: boolean;
}
