// US26 equipment requests (SCRUM-94): the shapes of SCRUM-109's API (§3 "Equipment requests") and
// SCRUM-110's GET /api/v1/me/equipment-events; US5's availability check (SCRUM-125); US27's reservations
// (SCRUM-131).

export type LineStatus = "pending" | "approved" | "rejected";

export interface EquipmentType {
  id: string;
  name: string;
}

/** An event the coordinator can add lines to: assigned to them, planning or confirmed. */
export interface EquipmentEvent {
  id: string;
  name: string | null;
  start_at: string | null;
  status: string;
}

export interface EquipmentLine {
  id: string;
  event: { id: string; name: string | null; start_at: string | null };
  equipment_type: EquipmentType;
  quantity: number;
  notes: string | null;
  status: LineStatus;
  review_note: string | null;
  requested_by_user_id: string;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  /** US5 (SCRUM-125, D64): the latest availability check, or null if none since the line last changed. */
  availability_check: AvailabilityCheck | null;
  /** US27 (SCRUM-131): the line's reservation, or null. */
  reservation: Reservation | null;
  created_at: string;
  updated_at: string;
}

export interface Reservation {
  quantity: number;
  reserved_by_user_id: string;
  reserved_at: string;
  // D75: nothing cancels an event yet (US9), so a cancelled event's reservation counts as released.
  released_because_event_cancelled: boolean;
}

export interface AvailabilityCheck {
  sufficient: boolean;
  shortfall: number;
  checked_by_user_id: string;
  checked_at: string;
}

/** POST /api/v1/equipment-lines/{id}/availability-check (US5, SCRUM-125): the full result. */
export interface EquipmentAvailability extends AvailabilityCheck {
  line_id: string;
  equipment_type: { id: string; name: string; storage_location: string | null };
  window: { starts_at: string; ends_at: string };
  requested: number;
  total: number;
  out_of_service: number;
  reserved_elsewhere: number;
  available: number;
}

/** Add and edit body. `quantity` can be what was typed, so the API names an invalid one (TC-US26-07). */
export interface EquipmentLineWrite {
  equipment_type_id?: string;
  quantity?: number | string;
  notes: string | null;
}

export interface EquipmentReviewWrite {
  decision: "approved" | "rejected";
  note?: string;
}

export interface LineFormValues {
  typeId: string;
  quantity: string;
  notes: string;
}

/** US14 (SCRUM-134): a Tech support staff member, or the coordinator who acted. */
export interface Person {
  id: string;
  name: string;
}

/** GET /api/v1/events/{id}/tech-staff, and POST's answer. */
export interface TechStaff {
  // D80: an approved equipment line, on a planning or confirmed event.
  eligible: boolean;
  assigned: { staff: Person; assigned_by: Person; assigned_at: string }[];
  // Not on an overlapping event (D81), nor assigned here; empty while not eligible.
  available: Person[];
  // Newest first (AC 6).
  log: { action: "assigned" | "unassigned"; staff: Person; by: Person; at: string }[];
}
