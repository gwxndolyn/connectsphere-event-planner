// Shapes from backend/app/event/cancellation_schemas.py (US9, SCRUM-12).
import type { EventRequestStatus } from "../eventRequest/types";

export interface CancellationPerson {
  id: string;
  name: string;
}

export interface Cancellation {
  id: string;
  event_id: string;
  event_name: string | null;
  request_reference: string | null;
  // The event's status after the call, so the screen can show Cancelled without reading the request again.
  event_status: EventRequestStatus;
  status: "pending" | "approved" | "rejected";
  reason: string;
  requested_by: CancellationPerson;
  requested_at: string;
  decided_by: CancellationPerson | null;
  decided_at: string | null;
  rejection_reason: string | null;
  // AC 3: the coordinator cancelled it themselves.
  direct: boolean;
}
