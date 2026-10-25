import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { formatEventDate } from "../registration/datetime";
import { equipmentApi, equipmentErrorMessage, eventLabel } from "./equipmentApi";
import type { EquipmentLine, EquipmentReviewWrite } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";

function lineName(line: EquipmentLine): string {
  return `${line.equipment_type.name} for ${eventLabel(line.event)}`;
}

function queueErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === "FORBIDDEN") return "Only Tech support can review equipment requests.";
  return equipmentErrorMessage(error);
}

/**
 * US26 AC 3 (SCRUM-110): Tech support's queue of pending lines, oldest first as the API returns them.
 * Each is approved for its full quantity or rejected (AC 6), with an optional note (D43); the requesting
 * coordinator is notified by the API (AC 5).
 */
export function EquipmentQueue() {
  const [lines, setLines] = useState<EquipmentLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [sending, setSending] = useState<string | null>(null);
  // US16b D51: a line this user requested, or for an event they coordinate, says so on its row.
  const [refusals, setRefusals] = useState<Record<string, string>>({});

  async function load() {
    try {
      setLines(await equipmentApi.queue());
    } catch (reason) {
      setError(queueErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let current = true;
    equipmentApi
      .queue()
      .then((result) => {
        if (current) setLines(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(queueErrorMessage(reason));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, []);

  async function review(line: EquipmentLine, decision: EquipmentReviewWrite["decision"]) {
    setError(null);
    setNotice(null);
    setRefusals((current) => {
      const rest = { ...current };
      delete rest[line.id];
      return rest;
    });
    setSending(line.id);
    const note = (notes[line.id] ?? "").trim();
    try {
      // Approval is always the line's full current quantity (AC 6), and the coordinator can edit a
      // pending line after this queue loaded. So check the line is unchanged before reviewing it, and
      // otherwise show what it is now (PR #78 review).
      const fresh = await equipmentApi.queue();
      const current = fresh.find((l) => l.id === line.id);
      if (!current || current.updated_at !== line.updated_at) {
        setLines(fresh);
        setError(
          current
            ? `${lineName(current)} changed since you loaded it: it's now Quantity ${current.quantity}. Check it, then choose again.`
            : `${lineName(line)} is no longer waiting for review: it was reviewed, or the coordinator removed it.`,
        );
        return;
      }
      await equipmentApi.review(line.id, note ? { decision, note } : { decision });
      setLines((current) => current.filter((l) => l.id !== line.id));
      setNotice(`${decision === "approved" ? "Approved" : "Rejected"}: ${lineName(line)}.`);
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "SELF_DECISION_NOT_ALLOWED") {
        setRefusals((current) => ({
          ...current,
          [line.id]: "Another Tech support user must review this line, because you requested it or coordinate its event.",
        }));
        return;
      }
      setError(queueErrorMessage(reason));
      // LINE_NOT_PENDING: reviewed elsewhere meanwhile, so show the queue as it is now.
      await load();
    } finally {
      setSending(null);
    }
  }

  return (
    <main className="request-page">
      <div className="request-page__heading">
        <div>
          <span className="request-page__eyebrow">EQUIPMENT</span>
          <h1>Equipment requests to review</h1>
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

      {loading ? (
        <p className="request-empty">Loading equipment requests…</p>
      ) : lines.length === 0 ? (
        <p className="request-empty">No equipment requests are waiting for review.</p>
      ) : (
        <ul className="venue-booking-list" aria-label="Pending equipment requests">
          {lines.map((line) => (
            <li key={line.id} className="venue-booking-row" aria-label={lineName(line)}>
              <div className="venue-booking-row__main">
                <strong>{lineName(line)}</strong>
                {line.event.start_at && <span>{formatEventDate({ startsAt: line.event.start_at, endsAt: line.event.start_at })}</span>}
                <span>Quantity {line.quantity}</span>
                {line.notes && <span>“{line.notes}”</span>}
                {refusals[line.id] && (
                  <span className="venue-booking-row__error" role="alert">
                    {refusals[line.id]}
                  </span>
                )}
              </div>
              <div className="request-field">
                <label htmlFor={`equipment-note-${line.id}`}>Note</label>
                <textarea
                  id={`equipment-note-${line.id}`}
                  rows={2}
                  value={notes[line.id] ?? ""}
                  onChange={(changed) => setNotes((current) => ({ ...current, [line.id]: changed.target.value }))}
                />
              </div>
              <button
                type="button"
                className="request-button request-button--primary"
                disabled={sending === line.id}
                onClick={() => void review(line, "approved")}
              >
                Approve
              </button>
              <button
                type="button"
                className="request-button request-button--secondary"
                disabled={sending === line.id}
                onClick={() => void review(line, "rejected")}
              >
                Reject
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
