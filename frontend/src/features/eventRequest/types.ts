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

// The assigned coordinator as the organiser sees them: a name, never an email (SCRUM-13 AC 8).
export interface AssignedCoordinator {
  id: string;
  name: string;
}

export interface EventRequest extends EventRequestWrite {
  id: string;
  status: EventRequestStatus;
  created_by_user_id: string | null;
  submitted_by_user_id: string | null;
  submitted_at: string | null;
  request_reference: string | null;
  created_at: string;
  // null = unassigned (SCRUM-13).
  coordinator: AssignedCoordinator | null;
}

export interface QueuePerson {
  id: string;
  name: string;
  email: string;
}

// A row of the Coordinator Lead's unassigned queue (SCRUM-13 AC 2).
export interface UnassignedRequest extends EventRequest {
  organiser: QueuePerson | null;
}

export interface UnassignedRequestsResponse {
  event_requests: UnassignedRequest[];
}

// A picker row: the coordinator and how many events they are currently planning (SCRUM-67, D30).
export interface CoordinatorOption extends QueuePerson {
  planning_count: number;
}

export interface CoordinatorOptionsResponse {
  coordinators: CoordinatorOption[];
}

// A row of the Lead's Assigned tab (SCRUM-86 AC 2): `event_date` is the start date, else the first
// preferred date, null when neither is set.
export interface AssignedRequest extends EventRequest {
  event_date: string | null;
}

export interface AssignedRequestsResponse {
  event_requests: AssignedRequest[];
}

// One Assignment History entry (SCRUM-69 AC 3), newest first as the API returns them.
export interface AssignmentRecord {
  id: string;
  kind: "assignment" | "reassignment";
  assigned_by: QueuePerson;
  coordinator: QueuePerson;
  created_at: string;
}

export interface AssignmentHistoryResponse {
  assignments: AssignmentRecord[];
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

export interface ClarificationThread {
  clarifications: Clarification[];
}
