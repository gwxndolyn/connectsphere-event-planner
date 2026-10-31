import { useEffect, useState } from "react";
import { formatEventDate } from "../registration/datetime";
import { equipmentApi, equipmentErrorMessage, eventLabel, lineStatusLabel, toLineBody } from "./equipmentApi";
import { LineForm } from "./LineForm";
import { RemoveLineDialog } from "./RemoveLineDialog";
import type { EquipmentEvent, EquipmentLine, EquipmentType, LineFormValues } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";

const BLANK: LineFormValues = { typeId: "", quantity: "", notes: "" };

// Reuses the venue booking badges: pending looks like a Requested booking.
const BADGE: Record<EquipmentLine["status"], string> = { pending: "requested", approved: "approved", rejected: "rejected" };

function formValues(line: EquipmentLine): LineFormValues {
  return { typeId: line.equipment_type.id, quantity: String(line.quantity), notes: line.notes ?? "" };
}

/**
 * US26 (SCRUM-110): the coordinator picks one of their events that can take equipment, sees its lines
 * with their status and Tech support's note, adds lines, and edits or removes pending ones (AC 1, 2, 4).
 */
export function EventEquipment() {
  // null while loading.
  const [events, setEvents] = useState<EquipmentEvent[] | null>(null);
  // The events or catalogue couldn't load: the alert says why, and there's no "none of your events".
  const [loadFailed, setLoadFailed] = useState(false);
  const [types, setTypes] = useState<EquipmentType[]>([]);
  const [eventId, setEventId] = useState("");
  const [lines, setLines] = useState<EquipmentLine[]>([]);
  const [linesLoading, setLinesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  // The line whose Remove is waiting for confirmation.
  const [confirming, setConfirming] = useState<EquipmentLine | null>(null);

  useEffect(() => {
    let current = true;
    Promise.all([equipmentApi.myEvents(), equipmentApi.types()])
      .then(([myEvents, catalogue]) => {
        if (!current) return;
        setEvents(myEvents);
        setTypes(catalogue);
      })
      .catch((reason: unknown) => {
        if (!current) return;
        setLoadFailed(true);
        setError(equipmentErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, []);

  useEffect(() => {
    if (!eventId) return;
    let current = true;
    equipmentApi
      .lines(eventId)
      .then((result) => {
        if (current) setLines(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(equipmentErrorMessage(reason));
      })
      .finally(() => {
        if (current) setLinesLoading(false);
      });
    return () => {
      current = false;
    };
  }, [eventId]);

  // After a refusal (e.g. Tech support reviewed the line meanwhile): show the lines as the API has them.
  async function reload() {
    try {
      setLines(await equipmentApi.lines(eventId));
    } catch (reason) {
      setError(equipmentErrorMessage(reason));
    }
  }

  function pick(id: string) {
    setEventId(id);
    setLines([]);
    setLinesLoading(Boolean(id));
    setEditingId(null);
    setError(null);
    setNotice(null);
  }

  async function add(values: LineFormValues) {
    setError(null);
    setNotice(null);
    const line = await equipmentApi.add(eventId, toLineBody(values));
    setLines((current) => [...current, line]);
  }

  async function save(line: EquipmentLine, values: LineFormValues) {
    setError(null);
    setNotice(null);
    try {
      const saved = await equipmentApi.edit(line.id, toLineBody(values));
      setLines((current) => current.map((l) => (l.id === saved.id ? saved : l)));
      setEditingId(null);
    } catch (reason) {
      void reload();
      throw reason;
    }
  }

  /** Runs once the coordinator confirms in the dialog; a refusal is rethrown for it to explain. */
  async function remove(line: EquipmentLine) {
    try {
      await equipmentApi.remove(line.id);
      setLines((current) => current.filter((l) => l.id !== line.id));
      setNotice(`Removed: ${line.equipment_type.name}.`);
      setConfirming(null);
    } catch (reason) {
      await reload();
      throw reason;
    }
  }

  const event = events?.find((e) => e.id === eventId);

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <span className="request-page__eyebrow">EQUIPMENT</span>
          <h1>Equipment for your events</h1>
        </div>
      </div>

      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="request-notice" role="status">
          {notice}
        </div>
      )}

      {loadFailed ? null : events === null ? (
        <p className="request-empty">Loading your events…</p>
      ) : events.length === 0 ? (
        <p className="request-empty">
          None of your events can take equipment requests yet. Only planning or confirmed events assigned to you are listed.
        </p>
      ) : (
        <>
          <div className="request-field">
            <label htmlFor="equipment-event">Event</label>
            <select id="equipment-event" value={eventId} onChange={(changed) => pick(changed.target.value)}>
              <option value="">Choose an event</option>
              {events.map((e) => (
                <option key={e.id} value={e.id}>
                  {eventLabel(e)}
                </option>
              ))}
            </select>
            {event && (
              <span>
                {event.start_at ? `${formatEventDate({ startsAt: event.start_at, endsAt: event.start_at })} · ` : ""}
                {event.status === "planning" ? "Planning" : "Confirmed"}
              </span>
            )}
          </div>

          {event && (
            <>
              <section className="venue-bookings" aria-labelledby="equipment-lines-title">
                <h2 id="equipment-lines-title">Equipment lines</h2>
                {linesLoading ? (
                  <p className="request-empty">Loading equipment lines…</p>
                ) : lines.length === 0 ? (
                  <p className="request-empty">No equipment requested for this event yet.</p>
                ) : (
                  <ul className="venue-booking-list" aria-label="Equipment lines">
                    {lines.map((line) => (
                      <li key={line.id} className="venue-booking-row" aria-label={line.equipment_type.name}>
                        {editingId === line.id ? (
                          <LineForm
                            label={`Edit ${line.equipment_type.name}`}
                            idPrefix={`equipment-edit-${line.id}`}
                            types={types}
                            initial={formValues(line)}
                            submitLabel="Save"
                            onSubmit={(values) => save(line, values)}
                            onCancel={() => setEditingId(null)}
                          />
                        ) : (
                          <>
                            <div className="venue-booking-row__main">
                              <strong>{line.equipment_type.name}</strong>
                              <span>Quantity {line.quantity}</span>
                              {line.notes && <span>“{line.notes}”</span>}
                              {line.review_note && <span>Tech support: {line.review_note}</span>}
                              {/* US27 AC 4 (SCRUM-132): Tech support has reserved it for the event. */}
                              {line.reservation && (
                                <span>
                                  {line.reservation.released_because_event_cancelled
                                    ? "Reservation released: the event was cancelled"
                                    : "Reserved"}
                                </span>
                              )}
                            </div>
                            <span className={`venue-booking-status venue-booking-status--${BADGE[line.status]}`}>
                              {lineStatusLabel(line.status)}
                            </span>
                            {line.status === "pending" && (
                              <>
                                <button
                                  type="button"
                                  className="request-button request-button--quiet"
                                  onClick={() => {
                                    setNotice(null);
                                    setEditingId(line.id);
                                  }}
                                >
                                  Edit
                                </button>
                                <button
                                  type="button"
                                  className="request-button request-button--quiet"
                                  onClick={() => {
                                    setNotice(null);
                                    setConfirming(line);
                                  }}
                                >
                                  Remove
                                </button>
                              </>
                            )}
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="venue-bookings" aria-labelledby="equipment-add-title">
                <h2 id="equipment-add-title">Add equipment</h2>
                <LineForm
                  key={eventId}
                  label="Add equipment"
                  idPrefix="equipment-add"
                  types={types}
                  initial={BLANK}
                  submitLabel="Add line"
                  onSubmit={add}
                  resetOnSuccess
                />
              </section>
            </>
          )}
        </>
      )}

      {confirming && (
        <RemoveLineDialog line={confirming} onConfirm={() => remove(confirming)} onClose={() => setConfirming(null)} />
      )}
    </main>
  );
}
