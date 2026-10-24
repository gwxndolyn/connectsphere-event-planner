import { ApiError, apiClient } from "../../api/client";
import type {
  EquipmentEvent,
  EquipmentLine,
  EquipmentLineWrite,
  EquipmentReviewWrite,
  EquipmentType,
  LineFormValues,
  LineStatus,
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

  review: (lineId: string, body: EquipmentReviewWrite) =>
    apiClient.post<EquipmentLine>(`/api/v1/equipment-lines/${lineId}/review`, body),
};

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
    case "FORBIDDEN":
      return "Equipment requests are for Coordinators and Tech support. Switch Acting as to one of them.";
    case "UNAUTHENTICATED":
      return "Set the dev user id for the role you're acting as in frontend/.env, then restart the frontend.";
    default:
      return FALLBACK_MESSAGE;
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
