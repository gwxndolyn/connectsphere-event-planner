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
}
