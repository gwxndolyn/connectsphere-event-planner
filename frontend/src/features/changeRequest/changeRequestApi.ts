import { ApiError, apiClient } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import { FIELD_LABELS, displayValue } from "../eventEdit/eventEditApi";
import type { EventRequest } from "../eventRequest/types";
import type { ChangeDecision, ChangeImpact, ChangeRequestReview, FieldChange, OrganiserChangeRequest, ReviewFlag } from "./types";

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

// --- US29b (SCRUM-143): the coordinator reviews and decides change requests, and the flags a significant one raises.

// The role the user is working in (the Role switcher), so one holding both sees only that role's requests.
export type DecidingRole = "coordinator" | "coordinator_lead";

export const changeReviewApi = {
  async pending(eventId: string | null, actingAs: DecidingRole): Promise<ChangeRequestReview[]> {
    const query = new URLSearchParams({ acting_as: actingAs });
    if (eventId) query.set("event_id", eventId);
    const body = await apiClient.get<{ change_requests: ChangeRequestReview[] }>(`/api/v1/change-requests?${query}`);
    return body.change_requests;
  },
  approve: (id: string) => apiClient.post<ChangeDecision>(`/api/v1/change-requests/${id}/approve`, {}),
  reject: (id: string, reason: string) => apiClient.post<ChangeDecision>(`/api/v1/change-requests/${id}/reject`, { reason }),
  async flags(eventId: string): Promise<ReviewFlag[]> {
    return (await apiClient.get<{ flags: ReviewFlag[] }>(`/api/v1/events/${eventId}/review-flags`)).flags;
  },
  clearFlag: (id: string, note: string) =>
    apiClient.post<ReviewFlag>(`/api/v1/review-flags/${id}/clear`, { note: note.trim() || null }),
};

export const REJECTION_MAX_LENGTH = 1000;

/**
 * A field as the coordinator reads it: the API's labels (US12's for a coordinator's edit, US29a's otherwise), so a
 * review flag, which carries only field names, reads like the request's table (Calvin's #127 review).
 */
export function reviewLabel(field: string): string {
  return FIELD_LABELS[field] ?? changeLabel(field);
}

/** A value in a request to decide: US12's words for its fields (e.g. In person), US29a's for the organiser's others. */
export function reviewValue(field: string, value: unknown): string {
  return field in FIELD_LABELS ? displayValue(field, value) : changeValue(field, value);
}

function count(n: number, one: string): string {
  return `${n} ${one}${n === 1 ? "" : "s"}`;
}

const STATUS_WORDS: Record<string, string> = {
  submitted: "Submitted",
  under_review: "Under Review",
  awaiting_clarification: "Awaiting Clarification",
  approved: "Approved",
  planning: "Planning",
  confirmed: "Confirmed",
  preparation: "Preparation",
  cancelled: "Cancelled",
  completed: "Completed",
  rejected: "Rejected",
};

export function statusWord(status: string): string {
  return STATUS_WORDS[status] ?? status;
}

/** D103 to D106 in words: what approving a significant request does, from the impact the API gives. */
export function impactParts(impact: ChangeImpact | null, status: string): string[] {
  if (!impact) return [];
  if (impact.venue_bookings === null) return ["The values change; nothing is flagged at this stage."];
  const parts: string[] = [];
  if (impact.status_after !== status) parts.push(`moves this event back to ${statusWord(impact.status_after)}`);
  const flagged = [
    impact.venue_bookings ? count(impact.venue_bookings, "venue booking") : null,
    impact.equipment_reservations ? count(impact.equipment_reservations, "equipment reservation") : null,
    impact.registrations ? `the event's registrations (${impact.registrations})` : null,
  ].filter((part): part is string => part !== null);
  if (flagged.length > 0) {
    const listed = flagged.length === 1 ? flagged[0] : `${flagged.slice(0, -1).join(", ")} and ${flagged.at(-1)}`;
    parts.push(`flags ${listed} for review`);
  }
  if (impact.safety_review_required) parts.push("needs a new safety review");
  return parts;
}

const STALE_REASONS: Record<string, string> = {
  changed: "changed since",
  not_at_this_stage: "not open at this stage",
  invalid: "no longer valid",
};

/** Why a decision was refused, in words (deviation 68's codes). */
export function decisionErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK;
  const status = typeof error.body.status === "string" ? error.body.status : "";
  switch (error.code) {
    case "CHANGE_REQUEST_STALE": {
      const fields = Array.isArray(error.body.fields) ? (error.body.fields as { field: string; reason: string }[]) : [];
      const named = fields.map((f) => `${reviewLabel(f.field)} (${STALE_REASONS[f.reason] ?? f.reason})`).join(", ");
      return `The event has changed since this was asked: ${named}. Reject it with a reason, and the organiser can ask again.`;
    }
    case "CHANGE_REQUEST_NOT_PENDING":
      return `This request was already ${status === "rejected" ? "rejected" : "approved"}.`;
    case "CHANGE_NOT_ALLOWED":
      return `Changes can't be approved while the event is in ${statusWord(status)}. The request can still be rejected.`;
    case "MISSING_REQUIRED_FIELD":
      return "Give a reason for rejecting.";
    case "INVALID_CHANGE_DECISION":
      return "The reason must be at most 1,000 characters.";
    case "SELF_DECISION_NOT_ALLOWED":
      return "You made this request, so a Coordinator Lead decides it.";
    case "FORBIDDEN":
      return "This isn't an action your role can take.";
    case "NOT_FOUND":
      return "This request isn't one you decide, or it no longer exists.";
    default:
      return FALLBACK;
  }
}

export function flagErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK;
  if (error.code === "FLAG_ALREADY_CLEARED") return "This was already marked reviewed.";
  if (error.code === "INVALID_REVIEW_FLAG") return "The note must be at most 1,000 characters.";
  if (error.code === "NOT_FOUND") return "This event isn't assigned to you.";
  return FALLBACK;
}
