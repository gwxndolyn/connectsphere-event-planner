import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { formatEventDate } from "../registration/datetime";
import type { EventRequest } from "../eventRequest/types";
import {
  AGENDA_EDITABLE,
  SESSION_TYPES,
  agendaApi,
  agendaErrorMessage,
  agendaFieldErrors,
  newSessionValues,
  sessionFormValues,
  sessionTimes,
  sessionTypeLabel,
  toSessionWrite,
  type SessionFormValues,
} from "./agendaApi";
import type { AgendaSession } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";
import "./agenda.css";

type FieldErrors = Partial<Record<keyof SessionFormValues, string>>;

/**
 * US15 (SCRUM-140): the event's agenda on the organiser's request (D97), in chronological order (AC 5). The request's
 * own Organiser adds, edits and deletes sessions while it's a draft or in planning (AC 1, D93); otherwise it's
 * read-only. The window, overlap and field rules are the API's (AC 2 to 4), shown on the form.
 */
export function EventAgenda({ event }: { event: EventRequest }) {
  const [sessions, setSessions] = useState<AgendaSession[] | null>(null);
  // null: the form is closed; "new": adding; otherwise the id of the session being edited.
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState<SessionFormValues>(() => newSessionValues(event));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const editable = AGENDA_EDITABLE.includes(event.status);

  useEffect(() => {
    let current = true;
    agendaApi
      .list(event.id)
      .then((result) => {
        if (current) setSessions(result);
      })
      .catch((reason: unknown) => {
        if (current) {
          setSessions([]);
          setError(agendaErrorMessage(reason));
        }
      });
    return () => {
      current = false;
    };
  }, [event.id]);

  async function reload() {
    setSessions(await agendaApi.list(event.id));
  }

  function open(session: AgendaSession | null) {
    setForm(session ? sessionFormValues(session) : newSessionValues(event));
    setFieldErrors({});
    setError(null);
    setEditing(session ? session.id : "new");
  }

  function update(key: keyof SessionFormValues, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    setFieldErrors(({ [key]: _cleared, ...rest }) => rest);
  }

  async function save(submitted: FormEvent<HTMLFormElement>) {
    submitted.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = toSessionWrite(form);
      if (editing === "new") await agendaApi.add(event.id, body);
      else if (editing) await agendaApi.edit(editing, body);
      setEditing(null);
      await reload();
    } catch (reason) {
      setFieldErrors(agendaFieldErrors(reason));
      setError(agendaErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function remove(session: AgendaSession) {
    setBusy(true);
    setError(null);
    try {
      await agendaApi.remove(session.id);
      if (editing === session.id) setEditing(null);
      await reload();
    } catch (reason) {
      setError(agendaErrorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  function field(label: string, key: keyof SessionFormValues, control: (props: Record<string, unknown>) => ReactNode, wide = false) {
    const message = fieldErrors[key];
    const id = `session-${key}`;
    return (
      <div className={`request-field${wide ? " request-field--wide" : ""}${message ? " request-field--invalid" : ""}`}>
        <label htmlFor={id}>{label}</label>
        {control({
          id,
          value: form[key],
          "aria-invalid": message ? true : undefined,
          "aria-describedby": message ? `${id}-error` : undefined,
          onChange: (changed: { target: { value: string } }) => update(key, changed.target.value),
        })}
        {message && (
          <span id={`${id}-error`} className="venue-field-error">
            {message}
          </span>
        )}
      </div>
    );
  }

  return (
    <section className="agenda" aria-labelledby="agenda-title">
      <div className="agenda__heading">
        <h2 id="agenda-title">Agenda</h2>
        {editable && editing === null && (
          <button type="button" className="request-button request-button--secondary" disabled={busy} onClick={() => open(null)}>
            Add session
          </button>
        )}
      </div>

      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      <p className="agenda__hint">
        {!editable
          ? "The agenda can be changed while the request is a draft or in planning."
          : event.status === "draft"
            ? "Sessions fall on one of the saved preferred dates, between the saved preferred times, one at a time."
            : "Sessions fall within the event's times, one at a time."}
      </p>

      {editing !== null && (
        <form className="request-form agenda__form" aria-label="Session" noValidate onSubmit={(submitted) => void save(submitted)}>
          <div className="venue-filters">
            {field("Title", "title", (props) => <input {...props} />, true)}
            {field("Session type", "session_type", (props) => (
              <select {...props}>
                {SESSION_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ))}
            {field("Speaker or presenter", "speaker_name", (props) => (
              <input placeholder={form.session_type === "break" ? "Not needed for a break" : undefined} {...props} />
            ))}
            {field("Date", "date", (props) => <input type="date" {...props} />)}
            {field("Start time", "startTime", (props) => <input type="time" {...props} />)}
            {field("End time", "endTime", (props) => <input type="time" {...props} />)}
          </div>
          <div className="request-form__actions">
            <button type="button" className="request-button request-button--quiet" disabled={busy} onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button type="submit" className="request-button request-button--primary" disabled={busy}>
              {busy ? "Saving…" : "Save session"}
            </button>
          </div>
        </form>
      )}

      {sessions === null ? (
        <p className="request-empty">Loading the agenda…</p>
      ) : sessions.length === 0 ? (
        <p className="request-empty">No sessions yet.</p>
      ) : (
        <ol className="venue-booking-list agenda__list" aria-label="Sessions">
          {sessions.map((session) => (
            <li key={session.id} className="venue-booking-row agenda__row">
              <div className="agenda__time">
                <span>{formatEventDate({ startsAt: session.starts_at, endsAt: session.ends_at })}</span>
                <strong>{sessionTimes(session)}</strong>
              </div>
              <div className="agenda__main">
                <h3>{session.title}</h3>
                <span>
                  {sessionTypeLabel(session.session_type)}
                  {session.speaker_name ? ` · ${session.speaker_name}` : ""}
                </span>
                {session.outside_window && <span className="agenda__outside">Outside the event's times</span>}
              </div>
              {editable && (
                <div className="agenda__actions">
                  <button
                    type="button"
                    className="request-button request-button--quiet"
                    aria-label={`Edit ${session.title}`}
                    disabled={busy}
                    onClick={() => open(session)}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="request-button request-button--quiet"
                    aria-label={`Delete ${session.title}`}
                    disabled={busy}
                    onClick={() => void remove(session)}
                  >
                    Delete
                  </button>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
