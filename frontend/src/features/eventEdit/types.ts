// Shapes from backend/app/event/edit_schemas.py (US12, SCRUM-15). Instants are ISO strings with an offset.
export type EventStatus = "planning" | "confirmed" | "cancelled" | "completed";

export interface CoordinatedEvent {
  id: string;
  name: string;
  status: EventStatus;
  // AC 1: true only while the event is in planning.
  editable: boolean;
  start_at: string;
  end_at: string;
}

export interface FieldChange {
  field: string;
  old_value: unknown;
  new_value: unknown;
}

export interface ChangeRequest {
  id: string;
  status: "pending_approval" | "approved" | "rejected";
  changes: FieldChange[];
  requested_by: { id: string; name: string };
  created_at: string;
}

export interface EventDetails extends CoordinatedEvent {
  request_reference: string | null;
  event_category: string | null;
  purpose: string | null;
  room_layout_preference: string | null;
  accessibility_needs: string | null;
  equipment_needs: string | null;
  join_link: string | null;
  capacity: number;
  expected_attendees: number | null;
  delivery_mode: "in_person" | "online";
  venue_name: string | null;
  room_number: string | null;
  pending_change_requests: ChangeRequest[];
}

export interface EventEditResult {
  outcome: "saved" | "pending_approval";
  message: string;
  event: EventDetails;
  change_request: ChangeRequest | null;
}

export interface AuditEntry {
  id: string;
  field: string;
  previous_value: unknown;
  new_value: unknown;
  user: { id: string; name: string };
  created_at: string;
  change_request_id: string | null;
  change_request_status: ChangeRequest["status"] | null;
}

// The form keeps every value as typed; eventEditApi.toEditBody turns it into the PATCH body.
export interface EventFormValues {
  name: string;
  event_category: string;
  purpose: string;
  date: string;
  startTime: string;
  endTime: string;
  capacity: string;
  expected_attendees: string;
  delivery_mode: string;
  room_layout_preference: string;
  accessibility_needs: string;
  equipment_needs: string;
  join_link: string;
}
