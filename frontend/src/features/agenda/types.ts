// Shapes from backend/app/agenda/schemas.py (US15, SCRUM-139).
export type SessionType = "presentation" | "workshop" | "panel" | "break" | "other";

export interface AgendaSession {
  id: string;
  event_id: string;
  title: string;
  session_type: SessionType;
  speaker_name: string | null;
  starts_at: string;
  ends_at: string;
  // D94: the event's window moved after it was saved, so it now falls outside it.
  outside_window: boolean;
}

export interface SessionWrite {
  title: string;
  session_type: SessionType;
  speaker_name: string | null;
  // null when the form's date or time is empty, so the API names the field (an empty string isn't a time).
  starts_at: string | null;
  ends_at: string | null;
}
