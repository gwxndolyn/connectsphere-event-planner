import { useEffect, useState } from "react";
import { formatEventDate, formatEventTimeRange, formatInstantDateTime } from "../registration/datetime";
import { eventRegistrationsApi, registrationsErrorMessage } from "./api";
import type { EventRegistrations, ManagedEvent, RegistrationFilter, RegistrationStatus } from "./types";
import "../eventRequest/eventRequests.css";
import "./eventRegistrations.css";

const STATUS_OPTIONS: { value: RegistrationStatus; label: string }[] = [
  { value: "confirmed", label: "Confirmed" },
  { value: "waitlisted", label: "Waitlisted" },
  { value: "offered", label: "Offered a place" },
  { value: "withdrawn", label: "Withdrawn" },
  { value: "declined", label: "Declined" },
  { value: "expired", label: "Offer expired" },
];

function statusText(status: RegistrationStatus): string {
  return STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
}

function timed(event: ManagedEvent) {
  return { startsAt: event.start_at, endsAt: event.end_at };
}

const DEFAULT_FILTER: RegistrationFilter = { status: "all", showAll: false };

/** US28 (SCRUM-96): pick an event you manage, then see who registered for it. */
export function EventRegistrationsPage() {
  const [events, setEvents] = useState<ManagedEvent[] | null>(null);
  const [selected, setSelected] = useState<ManagedEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    eventRegistrationsApi
      .listManagedEvents()
      .then((result) => {
        if (current) setEvents(result);
      })
      .catch((reason: unknown) => {
        if (current) {
          setEvents([]);
          setError(registrationsErrorMessage(reason));
        }
      });
    return () => {
      current = false;
    };
  }, []);

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <span className="request-page__eyebrow">REGISTRATIONS</span>
          <h1>{selected ? selected.name : "Event registrations"}</h1>
        </div>
        {selected && (
          <button type="button" className="request-button request-button--secondary" onClick={() => setSelected(null)}>
            All events
          </button>
        )}
      </div>

      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}

      {selected ? (
        <EventRegistrationsPanel key={selected.id} event={selected} />
      ) : events === null ? (
        <p className="request-empty">Loading events…</p>
      ) : events.length === 0 ? (
        !error && <p className="request-empty">No events to show yet. Registrations appear once an event is confirmed.</p>
      ) : (
        <section className="request-list" aria-label="Events you manage">
          {events.map((event) => (
            <button className="request-row" key={event.id} type="button" onClick={() => setSelected(event)}>
              <span className="request-row__main">
                <strong>{event.name}</strong>
                <span>
                  {formatEventDate(timed(event))} · {formatEventTimeRange(timed(event))}
                </span>
              </span>
              <span className={`request-status request-status--${event.status}`}>{event.status}</span>
              <span className="request-row__arrow" aria-hidden="true">›</span>
            </button>
          ))}
        </section>
      )}
    </main>
  );
}

function EventRegistrationsPanel({ event }: { event: ManagedEvent }) {
  const [filter, setFilter] = useState<RegistrationFilter>(DEFAULT_FILTER);
  const [data, setData] = useState<EventRegistrations | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    eventRegistrationsApi
      .list(event.id, filter)
      .then((result) => {
        if (current) {
          setData(result);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (current) setError(registrationsErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [event.id, filter]);

  if (error) {
    return (
      <div className="request-alert" role="alert">
        {error}
      </div>
    );
  }
  if (!data) return <p className="request-empty">Loading registrations…</p>;

  const { totals, registration_fields: questions, registrations } = data;
  return (
    <>
      <p className="registrations-when">
        {formatEventDate(timed(event))} · {formatEventTimeRange(timed(event))} · Capacity {event.capacity}
      </p>

      <dl className="registrations-totals" aria-label="Registration totals">
        <div>
          <dt>Confirmed</dt>
          <dd>{totals.confirmed}</dd>
        </div>
        <div>
          <dt>Waitlisted</dt>
          <dd>{totals.waitlisted}</dd>
        </div>
        <div>
          <dt>Offered a place</dt>
          <dd>{totals.offered}</dd>
        </div>
        <div>
          <dt>Places left</dt>
          <dd>{totals.seats_remaining}</dd>
        </div>
      </dl>

      <section className="registrations-filters" aria-label="Registration filters">
        <label className="request-field">
          Status
          <select
            value={filter.status}
            onChange={(change) => setFilter({ ...filter, status: change.target.value as RegistrationFilter["status"] })}
          >
            <option value="all">All statuses</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="registrations-toggle">
          <input
            type="checkbox"
            checked={filter.showAll}
            disabled={filter.status !== "all"}
            onChange={(change) => setFilter({ ...filter, showAll: change.target.checked })}
          />
          Show all, including withdrawn and declined
        </label>
      </section>

      {registrations.length === 0 ? (
        <p className="request-empty">No registrations match.</p>
      ) : (
        <div className="registrations-table-wrap">
          <table className="registrations-table" aria-label="Registrants">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Email</th>
                <th scope="col">Status</th>
                <th scope="col">Registered</th>
                <th scope="col">Waitlist position</th>
                {questions.map((question) => (
                  <th scope="col" key={question.field_key}>
                    {question.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {registrations.map((row) => (
                <tr key={row.registration_id}>
                  <td>{row.attendee_name ?? "—"}</td>
                  <td>{row.attendee_email}</td>
                  <td>
                    {statusText(row.status)}
                    {row.offer_expires_at && (
                      <span className="registrations-note">until {formatInstantDateTime(row.offer_expires_at)}</span>
                    )}
                  </td>
                  <td>{formatInstantDateTime(row.registered_at)}</td>
                  <td>{row.waitlist_position ?? "—"}</td>
                  {questions.map((question) => (
                    <td key={question.field_key}>{row.answers[question.field_key] || "—"}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
