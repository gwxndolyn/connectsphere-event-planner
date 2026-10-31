import { useEffect, useId, useState } from "react";
import { formatEventDate, formatInstantDateTime } from "../registration/datetime";
import { equipmentApi, equipmentErrorMessage, eventLabel } from "./equipmentApi";
import type { EquipmentLine } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";

function lineName(line: EquipmentLine): string {
  return `${line.equipment_type.name} for ${eventLabel(line.event)}`;
}

/** Reserved (and when), released because its event was cancelled (D75), or not reserved. */
function reservationState(line: EquipmentLine): string {
  if (!line.reservation) return "Not reserved";
  if (line.reservation.released_because_event_cancelled) return "Released: the event was cancelled";
  return `Reserved ${formatInstantDateTime(line.reservation.reserved_at)}`;
}

interface ApprovedLinesProps {
  // Bumped by the review queue when it approves a line, so the new line shows here to reserve.
  version: number;
}

/**
 * US27 (SCRUM-132): Tech support's approved lines, each reserved for its full quantity (AC 1, 6) or
 * released (AC 5). A reservation the API refuses for want of stock says how short it is, on its row (AC 2).
 */
export function ApprovedLines({ version }: ApprovedLinesProps) {
  const titleId = useId();
  const [lines, setLines] = useState<EquipmentLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    equipmentApi
      .approved()
      .then((result) => {
        if (current) {
          setLines(result);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (current) setError(equipmentErrorMessage(reason));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [version]);

  async function act(line: EquipmentLine, action: "reserve" | "release") {
    setRowErrors((current) => {
      const rest = { ...current };
      delete rest[line.id];
      return rest;
    });
    setBusy(line.id);
    try {
      if (action === "reserve") {
        const reserved = await equipmentApi.reserve(line.id);
        setLines((current) => current.map((l) => (l.id === line.id ? reserved : l)));
      } else {
        await equipmentApi.release(line.id);
        setLines((current) => current.map((l) => (l.id === line.id ? { ...l, reservation: null } : l)));
      }
    } catch (reason) {
      setRowErrors((current) => ({ ...current, [line.id]: equipmentErrorMessage(reason) }));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-labelledby={titleId}>
      <h2 id={titleId} className="venue-catalogue__title">
        Approved: to reserve
      </h2>
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {loading ? (
        <p className="request-empty">Loading approved equipment requests…</p>
      ) : lines.length === 0 ? (
        !error && <p className="request-empty">No approved equipment requests to reserve.</p>
      ) : (
        <ul className="venue-booking-list" aria-label="Approved equipment requests">
          {lines.map((line) => {
            const reservation = line.reservation;
            return (
              <li key={line.id} className="venue-booking-row" aria-label={lineName(line)}>
                <div className="venue-booking-row__main">
                  <strong>{lineName(line)}</strong>
                  {line.event.start_at && (
                    <span>{formatEventDate({ startsAt: line.event.start_at, endsAt: line.event.start_at })}</span>
                  )}
                  <span>Quantity {line.quantity}</span>
                  <span>{reservationState(line)}</span>
                  {rowErrors[line.id] && (
                    <span className="venue-booking-row__error" role="alert">
                      {rowErrors[line.id]}
                    </span>
                  )}
                </div>
                {!reservation && (
                  <button
                    type="button"
                    className="request-button request-button--primary"
                    disabled={busy === line.id}
                    onClick={() => void act(line, "reserve")}
                  >
                    Reserve
                  </button>
                )}
                {reservation && !reservation.released_because_event_cancelled && (
                  <button
                    type="button"
                    className="request-button request-button--secondary"
                    disabled={busy === line.id}
                    onClick={() => void act(line, "release")}
                  >
                    Release
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
