// US26 equipment requests (SCRUM-94): the shapes of SCRUM-109's API (§3 "Equipment requests") and
// SCRUM-110's GET /api/v1/me/equipment-events.

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
  created_at: string;
  updated_at: string;
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
