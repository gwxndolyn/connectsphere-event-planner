import { ApiError, apiClient } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import type { EventRequest } from "../eventRequest/types";
import type { FieldChange, OrganiserChangeRequest } from "./types";

// US29a routes are the organiser's (X-User-Id or a token), for their own events only.
export const changeRequestApi = {
  async mine(eventId: string): Promise<OrganiserChangeRequest[]> {
    const body = await apiClient.get<{ change_requests: OrganiserChangeRequest[] }>(`/api/v1/me/change-requests?event_id=${eventId}`);
    return body.change_requests;
  },

  create: (eventId: string, changes: Record<string, unknown>, reason: string) =>
    apiClient.post<OrganiserChangeRequest>(`/api/v1/event-requests/${eventId}/change-requests`, { changes, reason }),
};

// AC 1: Submitted or later, not Rejected, Cancelled or Completed.
export const REQUESTABLE = ["submitted", "under_review", "awaiting_clarification", "approved", "planning", "confirmed"];
const PLANNED = ["planning", "confirmed"];

export interface ChangeFormValues {
  name: string;
  event_category: string;
  purpose: string;
  preferred_date: string;
  preferred_start_time: string;
  preferred_end_time: string;
  date: string;
  startTime: string;
  endTime: string;
  expected_attendees: string;
  room_layout_preference: string;
  accessibility_needs: string;
  equipment_needs: string;
}

export function isPlanned(event: EventRequest): boolean {
  return PLANNED.includes(event.status);
}

const SGT_PARTS = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Singapore",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function singapore(iso: string | null | undefined): { date: string; time: string } {
  if (!iso) return { date: "", time: "" };
  const parts = Object.fromEntries(SGT_PARTS.formatToParts(new Date(iso)).map((part) => [part.type, part.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

export function changeFormValues(event: EventRequest): ChangeFormValues {
  const start = singapore(event.start_at);
  return {
    name: event.name ?? "",
    event_category: event.event_category ?? "",
    purpose: event.purpose ?? "",
    preferred_date: event.preferred_dates?.[0] ?? "",
    preferred_start_time: event.preferred_start_time?.slice(0, 5) ?? "",
    preferred_end_time: event.preferred_end_time?.slice(0, 5) ?? "",
    date: start.date,
    startTime: start.time,
    endTime: singapore(event.end_at).time,
    expected_attendees: event.expected_attendees == null ? "" : String(event.expected_attendees),
    room_layout_preference: event.room_layout_preference ?? "",
    accessibility_needs: event.accessibility_needs ?? "",
    equipment_needs: event.equipment_needs ?? "",
  };
}

/**
 * The `changes` body: only fields that differ from the event, as the API names them. A planned event sends its
 * start and end (+08:00, D9); a request sends preferences, keeping any other preferred dates it already has.
 */
export function toChanges(event: EventRequest, initial: ChangeFormValues, form: ChangeFormValues): Record<string, unknown> {
  const changes: Record<string, unknown> = {};
  for (const key of ["name", "event_category", "purpose", "room_layout_preference", "accessibility_needs", "equipment_needs"] as const) {
    if (form[key] !== initial[key]) changes[key] = form[key].trim() || null;
  }
  if (form.expected_attendees !== initial.expected_attendees) {
    const value = form.expected_attendees.trim();
    changes.expected_attendees = /^-?\d+$/.test(value) ? Number(value) : value || null;
  }
  if (isPlanned(event)) {
    const instant = (time: string) => (form.date && time ? `${form.date}T${time}:00+08:00` : null);
    if (form.date !== initial.date || form.startTime !== initial.startTime) changes.start_at = instant(form.startTime);
    if (form.date !== initial.date || form.endTime !== initial.endTime) changes.end_at = instant(form.endTime);
  } else {
    if (form.preferred_date !== initial.preferred_date) {
      const others = (event.preferred_dates ?? []).slice(1).filter((d) => d !== form.preferred_date);
      changes.preferred_dates = form.preferred_date ? [form.preferred_date, ...others] : [];
    }
    for (const key of ["preferred_start_time", "preferred_end_time"] as const) {
      if (form[key] !== initial[key]) changes[key] = form[key] || null;
    }
  }
  return changes;
}

const LABELS: Record<string, string> = {
  name: "Event name",
  event_category: "Event category",
  purpose: "Purpose / description",
  preferred_dates: "Preferred dates",
  preferred_start_time: "Preferred start time",
  preferred_end_time: "Preferred end time",
  start_at: "Start time",
  end_at: "End time",
  expected_attendees: "Expected attendees",
  room_layout_preference: "Room layout preference",
  accessibility_needs: "Accessibility needs",
  equipment_needs: "Equipment needs",
};

export function changeLabel(field: string): string {
  return LABELS[field] ?? field;
}

/** A value as the organiser reads it, current or proposed. */
export function changeValue(field: string, value: unknown): string {
  if (value === null || value === undefined || value === "" || (Array.isArray(value) && value.length === 0)) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if ((field === "start_at" || field === "end_at") && typeof value === "string") return formatInstantDateTime(value);
  if (typeof value === "string" && /^\d{2}:\d{2}(:\d{2})?$/.test(value)) return value.slice(0, 5);
  return String(value);
}

/** Each field to be sent with its value now and the value proposed (AC 2), before anything is sent. */
export function previewChanges(event: EventRequest, changes: Record<string, unknown>): FieldChange[] {
  const current = event as unknown as Record<string, unknown>;
  return Object.entries(changes).map(([field, new_value]) => ({ field, old_value: current[field] ?? null, new_value }));
}

const STATUS: Record<OrganiserChangeRequest["status"], string> = {
  pending_approval: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

export function changeStatusLabel(status: OrganiserChangeRequest["status"]): string {
  return STATUS[status] ?? status;
}

const FALLBACK = "The request could not be completed. Check the backend connection and try again.";

export function changeRequestErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK;
  switch (error.code) {
    case "MISSING_REQUIRED_FIELD":
      return error.fields.includes("reason") && !error.fields.includes("changes")
        ? "Give a reason for the change."
        : "Change at least one detail, and give a reason.";
    case "INVALID_CHANGE_REQUEST":
      return "Nothing was sent. Review the fields marked below and try again.";
    case "NO_CHANGES":
      return "Every value is the same as now. Change at least one detail.";
    case "CHANGE_NOT_ALLOWED":
      return "Changes can't be requested for this event any more.";
    case "NOT_FOUND":
      return "This event isn't yours, or it no longer exists.";
    default:
      return FALLBACK;
  }
}

/** The API's message per field, keyed by the form's own field. */
export function changeFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  if (error.code === "MISSING_REQUIRED_FIELD" && error.fields.includes("reason")) return { reason: "Give a reason for the change." };
  const errors = error.body.errors;
  if (error.code !== "INVALID_CHANGE_REQUEST" || !errors || typeof errors !== "object") return {};
  const form: Record<string, string> = {
    preferred_dates: "preferred_date",
    start_at: "startTime",
    end_at: "endTime",
  };
  return Object.fromEntries(
    Object.entries(errors)
      .filter((entry): entry is [string, string] => typeof entry[1] === "string")
      .map(([field, message]) => [form[field] ?? field, message]),
  );
}
