import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { formatEventDate, formatEventTimeRange, formatInstantDateTime } from "../registration/datetime";
import {
  displayValue,
  eventEditApi,
  eventEditErrorMessage,
  eventEditFieldErrors,
  fieldLabel,
  formValues,
  statusLabel,
  toEditBody,
} from "./eventEditApi";
import type { AuditEntry, CoordinatedEvent, EventDetails, EventFormValues } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";
import "./eventEdit.css";

function timed(event: CoordinatedEvent) {
  return { startsAt: event.start_at, endsAt: event.end_at };
}

/** US12 (SCRUM-15): the coordinator's events past the request stage; one opens to view, edit and see its History. */
export function EventsPage() {
  const [events, setEvents] = useState<CoordinatedEvent[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    eventEditApi
      .myEvents()
      .then((result) => {
        if (current) setEvents(result);
      })
      .catch((reason: unknown) => {
        if (current) {
          setEvents([]);
          setError(eventEditErrorMessage(reason));
        }
      });
    return () => {
      current = false;
    };
  }, [selectedId]);

  if (selectedId) return <EventPanel key={selectedId} eventId={selectedId} onBack={() => setSelectedId(null)} />;

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <span className="request-page__eyebrow">EVENTS</span>
          <h1>Your events</h1>
        </div>
      </div>

      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}

      {events === null ? (
        <p className="request-empty">Loading your events…</p>
      ) : events.length === 0 ? (
        !error && <p className="request-empty">No events assigned to you are past the request stage yet.</p>
      ) : (
        <section className="request-list" aria-label="Your events">
          {events.map((event) => (
            <button className="request-row" key={event.id} type="button" onClick={() => setSelectedId(event.id)}>
              <span className="request-row__main">
                <strong>{event.name}</strong>
                <span>
                  {formatEventDate(timed(event))} · {formatEventTimeRange(timed(event))}
                </span>
              </span>
              <span className={`request-status request-status--${event.status}`}>{statusLabel(event.status)}</span>
              <span className="request-row__arrow" aria-hidden="true">›</span>
            </button>
          ))}
        </section>
      )}
    </main>
  );
}

type Tab = "details" | "history";

function EventPanel({ eventId, onBack }: { eventId: string; onBack: () => void }) {
  const [event, setEvent] = useState<EventDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ text: string; pending: boolean } | null>(null);
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<Tab>("details");

  useEffect(() => {
    let current = true;
    eventEditApi
      .details(eventId)
      .then((result) => {
        if (current) setEvent(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(eventEditErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [eventId]);

  async function save(initial: EventFormValues, values: EventFormValues) {
    const body = toEditBody(initial, values);
    const result = await eventEditApi.edit(eventId, body);
    setEvent(result.event);
    setNotice({ text: result.message, pending: result.outcome === "pending_approval" });
    setEditing(false);
  }

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <span className="request-page__eyebrow">EVENT{event?.request_reference ? ` · ${event.request_reference}` : ""}</span>
          <h1>{event?.name ?? "Event"}</h1>
        </div>
        <button type="button" className="request-button request-button--secondary" onClick={onBack}>
          All events
        </button>
      </div>

      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className={`request-notice${notice.pending ? " event-edit-notice--pending" : ""}`} role="status">
          {notice.text}
        </div>
      )}

      {event && (
        <>
          <div className="event-edit-toolbar">
            <span className={`request-status request-status--${event.status}`}>{statusLabel(event.status)}</span>
            <div className="event-edit-tabs" role="tablist" aria-label="Event views">
              {(["details", "history"] as const).map((name) => (
                <button
                  key={name}
                  type="button"
                  role="tab"
                  aria-selected={tab === name}
                  className={`request-button request-button--quiet${tab === name ? " event-edit-tab--current" : ""}`}
                  onClick={() => setTab(name)}
                >
                  {name === "details" ? "Details" : "History"}
                </button>
              ))}
            </div>
            {tab === "details" && !editing && (
              <button
                type="button"
                className="request-button request-button--primary"
                disabled={!event.editable}
                title={event.editable ? undefined : "Only events in planning can be edited."}
                onClick={() => {
                  setNotice(null);
                  setEditing(true);
                }}
              >
                Edit
              </button>
            )}
          </div>
          {!event.editable && tab === "details" && (
            <p className="request-empty">Only events in planning can be edited. This one is {statusLabel(event.status).toLowerCase()}.</p>
          )}

          {tab === "history" ? (
            <EventHistory eventId={event.id} />
          ) : editing ? (
            <EventEditForm event={event} onSave={save} onCancel={() => setEditing(false)} />
          ) : (
            <EventSummary event={event} />
          )}
        </>
      )}
    </main>
  );
}

function EventSummary({ event }: { event: EventDetails }) {
  const rows: [string, ReactNode][] = [
    ["Event name", event.name],
    ["Category", displayValue("event_category", event.event_category)],
    ["Purpose", displayValue("purpose", event.purpose)],
    ["Date and time", `${formatEventDate(timed(event))} · ${formatEventTimeRange(timed(event))}`],
    ["Capacity", event.capacity],
    ["Expected attendance", displayValue("expected_attendees", event.expected_attendees)],
    ["Delivery mode", displayValue("delivery_mode", event.delivery_mode)],
    ["Venue", event.venue_name ? `${event.venue_name}${event.room_number ? `, ${event.room_number}` : ""}` : "—"],
    ["Room layout", displayValue("room_layout_preference", event.room_layout_preference)],
    ["Accessibility needs", displayValue("accessibility_needs", event.accessibility_needs)],
    ["Equipment needs", displayValue("equipment_needs", event.equipment_needs)],
    ["Join link", displayValue("join_link", event.join_link)],
  ];
  return (
    <>
      <section className="event-edit-details" aria-label="Event details">
        <dl>
          {rows.map(([term, value]) => (
            <div key={term}>
              <dt>{term}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      {event.pending_change_requests.length > 0 && (
        <section className="venue-bookings" aria-labelledby="event-change-requests-title">
          <h2 id="event-change-requests-title">Changes awaiting approval</h2>
          <ul className="venue-booking-list" aria-label="Changes awaiting approval">
            {event.pending_change_requests.map((request) => (
              <li key={request.id} className="venue-booking-row">
                <div className="venue-booking-row__main">
                  {request.changes.map((change) => (
                    <span key={change.field}>
                      <strong>{fieldLabel(change.field)}</strong>: {displayValue(change.field, change.old_value)} →{" "}
                      {displayValue(change.field, change.new_value)}
                    </span>
                  ))}
                  <span>
                    Requested by {request.requested_by.name}, {formatInstantDateTime(request.created_at)}
                  </span>
                </div>
                <span className="venue-booking-status venue-booking-status--requested">{statusLabel(request.status)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

const CRITICAL_NOTE = "Changing the date, times, capacity, expected attendance or delivery mode needs approval.";

function EventEditForm({
  event,
  onSave,
  onCancel,
}: {
  event: EventDetails;
  onSave: (initial: EventFormValues, values: EventFormValues) => Promise<void>;
  onCancel: () => void;
}) {
  const [initial] = useState(() => formValues(event));
  const [form, setForm] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [sending, setSending] = useState(false);

  function update(key: keyof EventFormValues, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    // Moving either end of the schedule can fix the other's error, as on the booking form (PR #83 review).
    const cleared = key === "date" || key === "startTime" || key === "endTime" ? ["startTime", "endTime"] : [key];
    setFieldErrors((current) => Object.fromEntries(Object.entries(current).filter(([field]) => !cleared.includes(field))));
  }

  async function handleSubmit(submitted: FormEvent<HTMLFormElement>) {
    submitted.preventDefault();
    setSending(true);
    setError(null);
    setFieldErrors({});
    try {
      await onSave(initial, form);
    } catch (reason) {
      setFieldErrors(eventEditFieldErrors(reason));
      setError(eventEditErrorMessage(reason));
    } finally {
      setSending(false);
    }
  }

  function field(label: string, key: keyof EventFormValues, control: (props: Record<string, unknown>) => ReactNode, wide = false) {
    const message = fieldErrors[key];
    const id = `event-edit-${key}`;
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
    <form className="request-form" aria-label="Edit event" noValidate onSubmit={(submitted) => void handleSubmit(submitted)}>
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      <p className="event-edit-hint">{CRITICAL_NOTE}</p>
      <div className="venue-filters">
        {field("Event name", "name", (props) => <input {...props} />)}
        {field("Category", "event_category", (props) => <input {...props} />)}
        {field("Delivery mode", "delivery_mode", (props) => (
          <select {...props}>
            <option value="in_person">In person</option>
            <option value="online">Online</option>
          </select>
        ))}
        {field("Date", "date", (props) => <input type="date" {...props} />)}
        {field("Start time", "startTime", (props) => <input type="time" {...props} />)}
        {field("End time", "endTime", (props) => <input type="time" {...props} />)}
        {field("Capacity", "capacity", (props) => <input inputMode="numeric" {...props} />)}
        {field("Expected attendance", "expected_attendees", (props) => <input inputMode="numeric" {...props} />)}
        {field("Room layout", "room_layout_preference", (props) => <input {...props} />)}
        {field("Purpose", "purpose", (props) => <textarea rows={3} {...props} />, true)}
        {field("Accessibility needs", "accessibility_needs", (props) => <textarea rows={2} {...props} />, true)}
        {field("Equipment needs", "equipment_needs", (props) => <textarea rows={2} {...props} />, true)}
        {field("Join link", "join_link", (props) => <input type="url" {...props} />, true)}
      </div>
      <div className="request-form__actions">
        <button type="button" className="request-button request-button--secondary" onClick={onCancel} disabled={sending}>
          Cancel
        </button>
        <button type="submit" className="request-button request-button--primary" disabled={sending}>
          {sending ? "Saving…" : "Save changes"}
        </button>
      </div>
    </form>
  );
}

function EventHistory({ eventId }: { eventId: string }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    eventEditApi
      .history(eventId)
      .then((result) => {
        if (current) setEntries(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(eventEditErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [eventId]);

  if (error) {
    return (
      <div className="request-alert" role="alert">
        {error}
      </div>
    );
  }
  if (entries === null) return <p className="request-empty">Loading history…</p>;
  if (entries.length === 0) return <p className="request-empty">No changes have been saved to this event yet.</p>;
  return (
    <section aria-label="History">
      <table className="event-edit-history">
        <thead>
          <tr>
            <th scope="col">When</th>
            <th scope="col">Who</th>
            <th scope="col">Field</th>
            <th scope="col">Previous value</th>
            <th scope="col">New value</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td>{formatInstantDateTime(entry.created_at)}</td>
              <td>
                {entry.user.name}
                <span className="event-edit-history__id">{entry.user.id}</span>
              </td>
              <td>
                {fieldLabel(entry.field)}
                {entry.change_request_status && (
                  <span className="venue-booking-status venue-booking-status--requested">{statusLabel(entry.change_request_status)}</span>
                )}
              </td>
              <td>{displayValue(entry.field, entry.previous_value)}</td>
              <td>{displayValue(entry.field, entry.new_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
