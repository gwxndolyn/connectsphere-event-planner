import { useEffect, useState } from "react";
import { formatInstantDateTime } from "../registration/datetime";
import { equipmentApi, techStaffErrorMessage } from "./equipmentApi";
import type { Person, TechStaff } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";

interface TechSupportStaffProps {
  eventId: string;
}

/**
 * US14 (SCRUM-135): on the coordinator's Equipment screen, the event's Technical support staff. Once it has
 * an approved equipment request (AC 1, D80), the coordinator ticks available staff and assigns them (AC 2,
 * 3), or unassigns someone (AC 5); reassigning is both. The log underneath has every change (AC 6). The
 * API decides who's available and refuses what's no longer allowed; its refusal shows on the section.
 */
export function TechSupportStaff({ eventId }: TechSupportStaffProps) {
  // null while loading.
  const [staff, setStaff] = useState<TechStaff | null>(null);
  const [ticked, setTicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let current = true;
    equipmentApi
      .techStaff(eventId)
      .then((result) => {
        if (current) setStaff(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(techStaffErrorMessage(reason, (id) => id));
      });
    return () => {
      current = false;
    };
  }, [eventId]);

  function nameOf(id: string): string {
    const people: Person[] = [...(staff?.available ?? []), ...(staff?.assigned.map((a) => a.staff) ?? [])];
    return people.find((person) => person.id === id)?.name ?? "Someone you picked";
  }

  /** Runs the change, then shows the section as the API has it, whether or not it was refused. */
  async function change(action: () => Promise<TechStaff | void>) {
    setError(null);
    setBusy(true);
    try {
      const result = await action();
      setTicked([]);
      setStaff(result ?? (await equipmentApi.techStaff(eventId)));
    } catch (reason) {
      setError(techStaffErrorMessage(reason, nameOf));
      try {
        setStaff(await equipmentApi.techStaff(eventId));
      } catch {
        // The refusal already says what went wrong.
      }
    } finally {
      setBusy(false);
    }
  }

  function toggle(id: string) {
    setTicked((current) => (current.includes(id) ? current.filter((t) => t !== id) : [...current, id]));
  }

  return (
    <section className="venue-bookings" aria-labelledby="equipment-tech-staff-title">
      <h2 id="equipment-tech-staff-title">Technical support</h2>
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {staff === null ? (
        !error && <p className="request-empty">Loading Technical support staff…</p>
      ) : (
        <>
          {staff.assigned.length === 0 ? (
            <p className="request-empty">No one assigned yet.</p>
          ) : (
            <ul className="venue-booking-list" aria-label="Assigned Tech support staff">
              {staff.assigned.map(({ staff: person, assigned_by, assigned_at }) => (
                <li key={person.id} className="venue-booking-row" aria-label={person.name}>
                  <div className="venue-booking-row__main">
                    <strong>{person.name}</strong>
                    <span>
                      Assigned by {assigned_by.name}, {formatInstantDateTime(assigned_at)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="request-button request-button--quiet"
                    aria-label={`Unassign ${person.name}`}
                    disabled={busy}
                    onClick={() => void change(() => equipmentApi.unassignTechStaff(eventId, person.id))}
                  >
                    Unassign
                  </button>
                </li>
              ))}
            </ul>
          )}

          {!staff.eligible ? (
            <p className="request-empty">Needs an approved equipment request first.</p>
          ) : staff.available.length === 0 ? (
            <p className="request-empty">No other Tech support staff are free at this event's times.</p>
          ) : (
            <fieldset className="venue-filters__tags">
              <legend>Available at this event's times</legend>
              {staff.available.map((person) => (
                <label key={person.id} className="venue-check">
                  <input type="checkbox" checked={ticked.includes(person.id)} onChange={() => toggle(person.id)} />
                  {person.name}
                </label>
              ))}
              <button
                type="button"
                className="request-button request-button--primary"
                disabled={busy || ticked.length === 0}
                // In the list's order, so the request doesn't depend on the order they were ticked.
                onClick={() =>
                  void change(() =>
                    equipmentApi.assignTechStaff(
                      eventId,
                      staff.available.filter((p) => ticked.includes(p.id)).map((p) => p.id),
                    ),
                  )
                }
              >
                Assign
              </button>
            </fieldset>
          )}

          {staff.log.length > 0 && (
            <>
              <h3>Log</h3>
              <ul className="venue-booking-list" aria-label="Assignment log">
                {staff.log.map((entry) => {
                  const text = `${entry.staff.name} ${entry.action} by ${entry.by.name}`;
                  return (
                    <li key={`${entry.action}-${entry.staff.id}-${entry.at}`} className="venue-booking-row" aria-label={text}>
                      <span>
                        {text}, {formatInstantDateTime(entry.at)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
