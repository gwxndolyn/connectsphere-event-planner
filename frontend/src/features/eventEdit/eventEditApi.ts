import { ApiError, apiClient } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import type { AuditEntry, CoordinatedEvent, EventDetails, EventEditResult, EventFormValues } from "./types";

// US12 routes are the coordinator's (X-User-Id or a token): only the event's assigned coordinator (D48).
export const eventEditApi = {
  async myEvents(): Promise<CoordinatedEvent[]> {
    return (await apiClient.get<{ events: CoordinatedEvent[] }>("/api/v1/me/coordinated-events")).events;
  },

  details: (eventId: string) => apiClient.get<EventDetails>(`/api/v1/events/${eventId}`),

  edit: (eventId: string, body: Record<string, unknown>) => apiClient.patch<EventEditResult>(`/api/v1/events/${eventId}`, body),

  async history(eventId: string): Promise<AuditEntry[]> {
    return (await apiClient.get<{ entries: AuditEntry[] }>(`/api/v1/events/${eventId}/history`)).entries;
  },
};

// Every event is in Singapore (D9): the form shows wall-clock times there and sends them with +08:00.
const SINGAPORE_OFFSET = "+08:00";
const SGT_PARTS = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Singapore",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function singaporeParts(iso: string): { date: string; time: string } {
  const parts = Object.fromEntries(SGT_PARTS.formatToParts(new Date(iso)).map((part) => [part.type, part.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

export function formValues(event: EventDetails): EventFormValues {
  const start = singaporeParts(event.start_at);
  return {
    name: event.name,
    event_category: event.event_category ?? "",
    purpose: event.purpose ?? "",
    date: start.date,
    startTime: start.time,
    endTime: singaporeParts(event.end_at).time,
    capacity: String(event.capacity),
    expected_attendees: event.expected_attendees == null ? "" : String(event.expected_attendees),
    delivery_mode: event.delivery_mode,
    room_layout_preference: event.room_layout_preference ?? "",
    accessibility_needs: event.accessibility_needs ?? "",
    equipment_needs: event.equipment_needs ?? "",
    join_link: event.join_link ?? "",
  };
}

function count(value: string): number | string {
  const trimmed = value.trim();
  return /^-?\d+$/.test(trimmed) ? Number(trimmed) : trimmed;
}

/**
 * The PATCH body: only the fields that differ from what was loaded, so an untouched field is never part
 * of a change request. Values are sent as typed, so the API checks them and names the field (AC 4).
 */
export function toEditBody(initial: EventFormValues, form: EventFormValues): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  for (const key of ["name", "event_category", "purpose", "delivery_mode", "room_layout_preference", "accessibility_needs", "equipment_needs", "join_link"] as const) {
    if (form[key] !== initial[key]) body[key] = form[key].trim() || null;
  }
  for (const key of ["capacity", "expected_attendees"] as const) {
    if (form[key] !== initial[key]) body[key] = form[key].trim() ? count(form[key]) : null;
  }
  const instant = (time: string) => (form.date && time ? `${form.date}T${time}:00${SINGAPORE_OFFSET}` : null);
  if (form.date !== initial.date || form.startTime !== initial.startTime) body.start_at = instant(form.startTime);
  if (form.date !== initial.date || form.endTime !== initial.endTime) body.end_at = instant(form.endTime);
  return body;
}

export const FIELD_LABELS: Record<string, string> = {
  name: "Event name",
  event_category: "Category",
  purpose: "Purpose",
  start_at: "Start time",
  end_at: "End time",
  capacity: "Capacity",
  expected_attendees: "Expected attendance",
  delivery_mode: "Delivery mode",
  room_layout_preference: "Room layout",
  accessibility_needs: "Accessibility needs",
  equipment_needs: "Equipment needs",
  join_link: "Join link",
};

export function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

/** A logged value as a person reads it: times in Singapore, modes in words, nothing as an em dash. */
export function displayValue(field: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if ((field === "start_at" || field === "end_at") && typeof value === "string") return formatInstantDateTime(value);
  if (field === "delivery_mode") return value === "online" ? "Online" : "In person";
  return String(value);
}

const STATUS_LABELS: Record<string, string> = {
  planning: "Planning",
  confirmed: "Confirmed",
  cancelled: "Cancelled",
  completed: "Completed",
  pending_approval: "Pending approval",
  approved: "Approved",
  rejected: "Rejected",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

const FALLBACK_MESSAGE = "The request could not be completed. Check the backend connection and try again.";

/** Readable text for the US12 routes' error codes. */
export function eventEditErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  switch (error.code) {
    case "INVALID_EVENT_EDIT":
      return "Nothing was saved. Review the fields marked below and try again.";
    case "EVENT_NOT_EDITABLE": {
      const status = typeof error.body.status === "string" ? statusLabel(error.body.status) : null;
      return `Only events in planning can be edited${status ? `; this one is ${status.toLowerCase()} now` : ""}.`;
    }
    case "NOT_FOUND":
      return "This event isn't assigned to you, or it no longer exists.";
    case "FORBIDDEN":
      return "Editing events is for Coordinators. Switch Acting as to Coordinator.";
    case "UNAUTHENTICATED":
      return "Set the dev user id for the role you're acting as in frontend/.env, then restart the frontend.";
    default:
      return FALLBACK_MESSAGE;
  }
}

/** The API's message per field, keyed by the form's own field: a time error shows on the time it concerns. */
export function eventEditFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.code !== "INVALID_EVENT_EDIT") return {};
  const errors = error.body.errors;
  if (!errors || typeof errors !== "object") return {};
  const byForm: Record<string, string> = {};
  for (const [field, message] of Object.entries(errors)) {
    if (typeof message !== "string") continue;
    byForm[field === "start_at" ? "startTime" : field === "end_at" ? "endTime" : field] = message;
  }
  return byForm;
}
