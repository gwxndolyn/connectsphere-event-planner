import { useEffect, useState } from "react";
import { ApiError, apiClient } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import type { EventRequest, Readiness } from "./types";

const CONFIRMABLE = new Set(["approved", "planning"]);

function confirmationError(error: unknown): string {
  if (!(error instanceof ApiError)) return "The request could not be completed. Check the backend connection and try again.";
  switch (error.code) {
    case "EVENT_NOT_READY":
      return "Some arrangements are still outstanding, so the event can't be confirmed yet.";
    case "CONFIRMATION_NOT_ALLOWED":
      return "This event can't be confirmed in its current status.";
    case "PREPARATION_NOT_ALLOWED":
      return "Only a confirmed event can move to Preparation.";
    case "NOT_FOUND":
      return "This event isn't assigned to you, so you can't confirm it.";
    default:
      return `The backend rejected the request (${error.status}).`;
  }
}

interface EventConfirmationProps {
  request: EventRequest;
  onChanged: (request: EventRequest) => void;
}

/**
 * US18 (SCRUM-85): the assigned coordinator's readiness list and Confirm event (AC 1-3, 5), then Start
 * preparation on a confirmed event (AC 6). Confirm stays disabled until every arrangement is complete:
 * the API refuses an incomplete event too, and nothing overrides it.
 */
export function EventConfirmation({ request, onChanged }: EventConfirmationProps) {
  const confirmable = CONFIRMABLE.has(request.status);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [loading, setLoading] = useState(confirmable);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Bumped by Check again, so the effect below reads the list once more.
  const [checks, setChecks] = useState(0);

  useEffect(() => {
    if (!confirmable) return;
    let current = true;
    apiClient
      .get<Readiness>(`/api/v1/event-requests/${request.id}/readiness`)
      .then((result) => {
        if (current) setReadiness(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(confirmationError(reason));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [confirmable, request.id, checks]);

  function checkAgain() {
    setLoading(true);
    setChecks((count) => count + 1);
  }

  async function act(action: "confirmation" | "preparation") {
    setBusy(true);
    setError(null);
    try {
      onChanged(await apiClient.post<EventRequest>(`/api/v1/event-requests/${request.id}/${action}`, {}));
    } catch (reason) {
      setError(confirmationError(reason));
      // The list may have changed under the coordinator (a Venue staff decision): show what is true now.
      if (reason instanceof ApiError && reason.code === "EVENT_NOT_READY") checkAgain();
    } finally {
      setBusy(false);
    }
  }

  if (request.status === "preparation") {
    return (
      <section className="request-confirm" aria-labelledby="request-confirm-title">
        <h2 id="request-confirm-title">Preparation</h2>
        <p role="status">This event is in Preparation. Venue staff and Technical support preparation updates are open.</p>
      </section>
    );
  }

  if (request.status === "confirmed") {
    return (
      <section className="request-confirm" aria-labelledby="request-confirm-title">
        <h2 id="request-confirm-title">Confirmed</h2>
        {error && <div className="request-alert" role="alert">{error}</div>}
        <p role="status">
          This event is confirmed{request.confirmed_at ? ` (${formatInstantDateTime(request.confirmed_at)})` : ""}. The
          organiser has been told its date, time and venue.
        </p>
        <div className="request-form__actions">
          <button className="request-button request-button--primary" type="button" disabled={busy} onClick={() => void act("preparation")}>
            {busy ? "Starting…" : "Start preparation"}
          </button>
        </div>
      </section>
    );
  }

  if (!confirmable) return null;

  return (
    <section className="request-confirm" aria-labelledby="request-confirm-title">
      <h2 id="request-confirm-title">Readiness to confirm</h2>
      {error && <div className="request-alert" role="alert">{error}</div>}
      {readiness === null ? (
        <p className="request-empty" role="status">{loading ? "Checking arrangements…" : "Readiness isn't available."}</p>
      ) : (
        <>
          <ul className="readiness-list" aria-label="Readiness">
            {readiness.items.map((item, index) => (
              <li className={`readiness-item readiness-item--${item.complete ? "complete" : "outstanding"}`} key={`${item.kind}-${index}`}>
                <span className="readiness-item__mark" aria-hidden="true">{item.complete ? "✓" : "✗"}</span>
                <span className="readiness-item__text">
                  <strong>{item.name}</strong>
                  <span className="readiness-item__state">{item.complete ? "Complete" : "Outstanding"}</span>
                  <span className="readiness-item__detail">{item.detail}</span>
                </span>
              </li>
            ))}
          </ul>
          <p className="request-notice">
            {readiness.ready
              ? "Every arrangement is complete. Confirming tells the organiser the date, time and venue."
              : "Confirming is blocked until every outstanding arrangement is complete. It can't be overridden."}
          </p>
        </>
      )}
      <div className="request-form__actions">
        <button className="request-button request-button--quiet" type="button" disabled={loading || busy} onClick={checkAgain}>
          Check again
        </button>
        <button
          className="request-button request-button--primary"
          type="button"
          disabled={!readiness?.ready || busy}
          onClick={() => void act("confirmation")}
        >
          {busy ? "Confirming…" : "Confirm event"}
        </button>
      </div>
    </section>
  );
}
