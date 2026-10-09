export type EventRequestStatus =
  | "draft"
  | "submitted"
  | "under_review"
  | "awaiting_clarification"
  | "approved"
  | "rejected"
  | "planning"
  | "confirmed"
  | "cancelled"
  | "completed";

export interface EventRequestWrite {
  name: string | null;
  event_category: string | null;
  purpose: string | null;
  preferred_dates: string[] | null;
  preferred_start_time: string | null;
  preferred_end_time: string | null;
  expected_attendees: number | null;
  room_layout_preference: string | null;
  accessibility_needs: string | null;
  equipment_needs: string | null;
  registration_required: boolean | null;
}

export interface EventRequest extends EventRequestWrite {
  id: string;
  status: EventRequestStatus;
  created_by_user_id: string | null;
  submitted_by_user_id: string | null;
  submitted_at: string | null;
  request_reference: string | null;
  created_at: string;
}

export interface EventRequestsResponse {
  event_requests: EventRequest[];
}
// Mirrors CLARIFICATION_SECTIONS in the backend (D13).
export type ClarificationSection =
  | "details"
  | "schedule"
  | "attendance"
  | "layout"
  | "accessibility"
  | "equipment"
  | "registration";

export interface Clarification {
  id: string;
  event_id: string;
  round: number;
  kind: "request" | "response";
  sections: ClarificationSection[] | null;
  comment: string;
  author_user_id: string;
  created_at: string;
}

export interface ClarificationSent {
  clarification: Clarification;
  status: EventRequestStatus;
}
