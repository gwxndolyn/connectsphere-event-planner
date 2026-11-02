import { ApiError, apiClient } from "../../api/client";
import { formatEventTimeRange } from "../registration/datetime";
import type { EventRequest } from "../eventRequest/types";
import type { AgendaSession, SessionType, SessionWrite } from "./types";

// US15 routes (SCRUM-139): anyone who can read the request lists its agenda; only its organiser changes it.
export const agendaApi = {
  async list(eventId: string): Promise<AgendaSession[]> {
    const body = await apiClient.get<{ sessions: AgendaSession[] }>(`/api/v1/event-requests/${eventId}/sessions`);
    return body.sessions;
  },

  add: (eventId: string, session: SessionWrite) =>
    apiClient.post<AgendaSession>(`/api/v1/event-requests/${eventId}/sessions`, session),

  edit: (sessionId: string, session: SessionWrite) => apiClient.patch<AgendaSession>(`/api/v1/event-sessions/${sessionId}`, session),

  remove: (sessionId: string) => apiClient.delete(`/api/v1/event-sessions/${sessionId}`),
};

// D93: the request's own Organiser changes the agenda while it's a draft or in planning.
export const AGENDA_EDITABLE = ["draft", "planning"];

// D96: the AC's types, plus Other; the form offers them in this order.
export const SESSION_TYPES: { value: SessionType; label: string }[] = [
  { value: "presentation", label: "Presentation" },
  { value: "workshop", label: "Workshop" },
  { value: "panel", label: "Panel" },
  { value: "break", label: "Break" },
  { value: "other", label: "Other" },
];

export function sessionTypeLabel(type: SessionType): string {
  return SESSION_TYPES.find((option) => option.value === type)?.label ?? type;
}

export interface SessionFormValues {
  title: string;
  session_type: SessionType;
  speaker_name: string;
  date: string;
  startTime: string;
  endTime: string;
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

/** A new session starts on the event's day: its own date once planned, else its first preferred date. */
export function newSessionValues(event: EventRequest): SessionFormValues {
  const date = event.start_at ? singapore(event.start_at).date : (event.preferred_dates?.[0] ?? "");
  return { title: "", session_type: "presentation", speaker_name: "", date, startTime: "", endTime: "" };
}

export function sessionFormValues(session: AgendaSession): SessionFormValues {
  const start = singapore(session.starts_at);
  return {
    title: session.title,
    session_type: session.session_type,
    speaker_name: session.speaker_name ?? "",
    date: start.date,
    startTime: start.time,
    endTime: singapore(session.ends_at).time,
  };
}

/**
 * The body: Singapore wall-clock times (+08:00, D9), both on the form's date. The API checks every rule. A missing
 * date or time is null: the API then names the field ("Give the session's start time."), where an empty string
 * would fail FastAPI's own parsing, with no code to show.
 */
export function toSessionWrite(values: SessionFormValues): SessionWrite {
  const instant = (time: string) => (values.date && time ? `${values.date}T${time}:00+08:00` : null);
  return {
    title: values.title,
    session_type: values.session_type,
    speaker_name: values.speaker_name.trim() || null,
    starts_at: instant(values.startTime),
    ends_at: instant(values.endTime),
  };
}

export function sessionTimes(session: { starts_at: string; ends_at: string }): string {
  return formatEventTimeRange({ startsAt: session.starts_at, endsAt: session.ends_at });
}

const FALLBACK = "The agenda could not be updated. Check the backend connection and try again.";

export function agendaErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK;
  switch (error.code) {
    case "INVALID_SESSION":
      return "Nothing was saved. Review the fields marked below and try again.";
    case "SESSION_OVERLAP": {
      // AC 4, D95: one session at a time, so name the one in the way.
      const clash = error.body.session as { title?: string; starts_at?: string; ends_at?: string } | undefined;
      if (!clash?.title || !clash.starts_at || !clash.ends_at) return "This overlaps another session. An event runs one session at a time.";
      return `This overlaps “${clash.title}” (${sessionTimes({ starts_at: clash.starts_at, ends_at: clash.ends_at })}). An event runs one session at a time.`;
    }
    case "AGENDA_NOT_EDITABLE":
      return "The agenda can't be changed any more: the request is no longer a draft or in planning.";
    case "NOT_FOUND":
      return "This session or request no longer exists.";
    default:
      return FALLBACK;
  }
}

/** The API's message per field, keyed by the form's own field: the times go on Start time and End time. */
export function agendaFieldErrors(error: unknown): Partial<Record<keyof SessionFormValues, string>> {
  if (!(error instanceof ApiError) || error.code !== "INVALID_SESSION") return {};
  const errors = error.body.errors;
  if (!errors || typeof errors !== "object") return {};
  const form: Record<string, keyof SessionFormValues> = { starts_at: "startTime", ends_at: "endTime" };
  return Object.fromEntries(
    Object.entries(errors)
      .filter((entry): entry is [string, string] => typeof entry[1] === "string")
      .map(([field, message]) => [form[field] ?? field, message]),
  );
}
