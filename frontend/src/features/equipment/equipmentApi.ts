import { ApiError, apiClient } from "../../api/client";
import type {
  EquipmentAvailability,
  EquipmentEvent,
  EquipmentLine,
  EquipmentLineWrite,
  EquipmentReviewWrite,
  EquipmentType,
  LineFormValues,
  LineStatus,
  TechStaff,
} from "./types";

// US26 routes identify the caller by X-User-Id (or a token): the event's assigned coordinator manages
// its lines (D20), Tech support reviews them (deviation 34).
export const equipmentApi = {
  async types(): Promise<EquipmentType[]> {
    return (await apiClient.get<{ equipment_types: EquipmentType[] }>("/api/v1/equipment-types")).equipment_types;
  },

  async myEvents(): Promise<EquipmentEvent[]> {
    return (await apiClient.get<{ events: EquipmentEvent[] }>("/api/v1/me/equipment-events")).events;
  },

  async lines(eventId: string): Promise<EquipmentLine[]> {
    return (await apiClient.get<{ lines: EquipmentLine[] }>(`/api/v1/events/${eventId}/equipment-lines`)).lines;
  },

  add: (eventId: string, body: EquipmentLineWrite) =>
    apiClient.post<EquipmentLine>(`/api/v1/events/${eventId}/equipment-lines`, body),

  edit: (lineId: string, body: EquipmentLineWrite) => apiClient.patch<EquipmentLine>(`/api/v1/equipment-lines/${lineId}`, body),

  async remove(lineId: string): Promise<void> {
    await apiClient.delete(`/api/v1/equipment-lines/${lineId}`);
  },

  async queue(): Promise<EquipmentLine[]> {
    return (await apiClient.get<{ lines: EquipmentLine[] }>("/api/v1/equipment-lines?status=pending")).lines;
  },

  // US27 (SCRUM-131): Tech support's approved lines, to reserve.
  async approved(): Promise<EquipmentLine[]> {
    return (await apiClient.get<{ lines: EquipmentLine[] }>("/api/v1/equipment-lines?status=approved")).lines;
  },

  // Always the line's full quantity (AC 6), so there's nothing to send.
  reserve: (lineId: string) => apiClient.post<EquipmentLine>(`/api/v1/equipment-lines/${lineId}/reservation`, {}),

  async release(lineId: string): Promise<void> {
    await apiClient.delete(`/api/v1/equipment-lines/${lineId}/reservation`);
  },

  review: (lineId: string, body: EquipmentReviewWrite) =>
    apiClient.post<EquipmentLine>(`/api/v1/equipment-lines/${lineId}/review`, body),

  // US5 (SCRUM-125): Tech support only; the outcome is recorded on the line (D64).
  checkAvailability: (lineId: string) =>
    apiClient.post<EquipmentAvailability>(`/api/v1/equipment-lines/${lineId}/availability-check`, {}),

  // US14 (SCRUM-134): the event's coordinator only (D20).
  techStaff: (eventId: string) => apiClient.get<TechStaff>(`/api/v1/events/${eventId}/tech-staff`),

  assignTechStaff: (eventId: string, staffUserIds: string[]) =>
    apiClient.post<TechStaff>(`/api/v1/events/${eventId}/tech-staff`, { staff_user_ids: staffUserIds }),

  async unassignTechStaff(eventId: string, staffUserId: string): Promise<void> {
    await apiClient.delete(`/api/v1/events/${eventId}/tech-staff/${staffUserId}`);
  },
};

/** "Sufficient" or "Short by N" (US5 AC 4). */
export function availabilityOutcome(check: { sufficient: boolean; shortfall: number }): string {
  return check.sufficient ? "Sufficient" : `Short by ${check.shortfall}`;
}

/**
 * The add or edit body. A whole number is sent as one, 0 and negatives included, and anything else as
 * typed: the API checks the quantity and names it (INVALID_EQUIPMENT_LINE, TC-US26-16), so the screen
 * doesn't repeat the rule. Blank type and quantity are left out, so the API names them too.
 */
export function toLineBody(form: LineFormValues): EquipmentLineWrite {
  const body: EquipmentLineWrite = { notes: form.notes.trim() || null };
  const quantity = form.quantity.trim();
  if (form.typeId) body.equipment_type_id = form.typeId;
  if (quantity) body.quantity = /^-?\d+$/.test(quantity) ? Number(quantity) : quantity;
  return body;
}

const STATUS_LABELS: Record<LineStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

export function lineStatusLabel(status: LineStatus): string {
  return STATUS_LABELS[status] ?? status;
}

export function eventLabel(event: { name: string | null }): string {
  return event.name || "Untitled event";
}

const FALLBACK_MESSAGE = "The request could not be completed. Check the backend connection and try again.";

/** Readable text for the equipment routes' error codes (§3, deviations 36 to 39). */
export function equipmentErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  const status = typeof error.body.status === "string" ? error.body.status.replaceAll("_", " ") : null;
  switch (error.code) {
    case "INVALID_EQUIPMENT_LINE":
      return "Review the fields marked below and try again.";
    case "DUPLICATE_EQUIPMENT_TYPE":
      return typeof error.body.message === "string" ? error.body.message : "This event already has a line for that equipment type.";
    case "LINE_NOT_PENDING":
      return `This line has already been reviewed${status ? ` (it's ${status} now)` : ""}, so it can't be changed.`;
    case "EVENT_NOT_ELIGIBLE":
      return `Equipment can only be requested for events in planning or confirmed${status ? `; this one is ${status}` : ""}.`;
    case "NOT_FOUND":
      return "This event or equipment line is no longer available. Reload and try again.";
    // US27 (SCRUM-131, deviation 54).
    case "INSUFFICIENT_EQUIPMENT": {
      const { available, requested, shortfall } = error.body;
      return `Short by ${String(shortfall)}: can't reserve. ${String(available)} available for ${String(requested)} requested.`;
    }
    case "LINE_NOT_APPROVED":
      return "Only an approved line can be reserved.";
    case "ALREADY_RESERVED":
      return "This line is already reserved. Reload to see it.";
    case "NOT_RESERVED":
      return "This line isn't reserved any more. Reload to see it.";
    case "FORBIDDEN":
      return "Equipment requests are for Coordinators and Tech support. Switch Acting as to one of them.";
    case "UNAUTHENTICATED":
      return "Set the dev user id for the role you're acting as in frontend/.env, then restart the frontend.";
    default:
      return FALLBACK_MESSAGE;
  }
}

/**
 * Readable text for the US14 routes' refusals (deviation 56), naming the staff concerned from `nameOf`.
 * Anything else reads as for the other equipment routes.
 */
export function techStaffErrorMessage(error: unknown, nameOf: (id: string) => string): string {
  if (!(error instanceof ApiError)) return equipmentErrorMessage(error);
  const ids = Array.isArray(error.body.staff_user_ids) ? error.body.staff_user_ids.map(String) : [];
  const names = ids.map(nameOf).join(", ") || "Someone you picked";
  const verb = ids.length > 1 ? "are" : "is";
  switch (error.code) {
    case "NO_APPROVED_TECH_REQUEST":
      return "Needs an approved equipment request first.";
    case "STAFF_UNAVAILABLE":
      return `${names} ${verb} now on another event at these times, so no one was assigned.`;
    case "ALREADY_ASSIGNED":
      return `${names} ${verb} already assigned to this event.`;
    case "INVALID_STAFF":
      return `${names} can't be assigned: not an active Tech support user.`;
    case "EVENT_STARTED":
      return "This event has already started, so its Technical support staff can't be changed.";
    case "NOT_ASSIGNED":
      return "That person isn't assigned to this event any more.";
    default:
      return equipmentErrorMessage(error);
  }
}

/** A message per API field name, for the form to show beside its input. */
export function equipmentFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  switch (error.code) {
    case "INVALID_EQUIPMENT_LINE": {
      const errors = error.body.errors;
      if (!errors || typeof errors !== "object") return {};
      return Object.fromEntries(
        Object.entries(errors).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
      );
    }
    case "DUPLICATE_EQUIPMENT_TYPE":
      return { equipment_type_id: equipmentErrorMessage(error) };
    default:
      return {};
  }
}
