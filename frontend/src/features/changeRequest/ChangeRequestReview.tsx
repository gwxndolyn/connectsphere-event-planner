import { useEffect, useRef, useState } from "react";
import { formatInstantDateTime } from "../registration/datetime";
import type { EventRequest } from "../eventRequest/types";
import {
  REJECTION_MAX_LENGTH,
  changeReviewApi,
  decisionErrorMessage,
  impactParts,
  reviewLabel,
  reviewValue,
  statusWord,
  type DecidingRole,
} from "./changeRequestApi";
import type { ChangeDecision, ChangeRequestReview as Review } from "./types";
import "./changeRequests.css";

interface ChangeRequestReviewProps {
  event: EventRequest;
  actingAs: DecidingRole;
  // The request the coordinator came to review from the queue: shown in view.
  focusId?: string | null;
  // The decision: the event as it left it, and what else it changed, so the screen's status, readiness and safety
  // outcome follow.
  onDecided: (decision: ChangeDecision) => void;
}

/**
 * US29b AC 1, 2 (SCRUM-143): the pending change requests on the event, for its assigned coordinator to approve or
 * reject. A significant one says what approving does (D103 to D106). Deviation 71: on the review screen between the
 * venue bookings and the safety review, next to the arrangements it affects; Approve takes a second click, and Reject
 * needs a reason first.
 */
function requestElementId(id: string): string {
  return `change-request-${id}`;
}

export function ChangeRequestReview({ event, actingAs, focusId, onDecided }: ChangeRequestReviewProps) {
  const [requests, setRequests] = useState<Review[] | null>(null);
  const [loads, setLoads] = useState(0);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Scrolled to the focused request already: a reload after a decision doesn't move the page again.
  const scrolled = useRef(false);

  useEffect(() => {
    let current = true;
    changeReviewApi
      .pending(event.id, actingAs)
      .then((found) => {
        if (current) setRequests(found);
      })
      .catch((reason: unknown) => {
        if (current) setError(decisionErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, [event.id, actingAs, loads]);

  useEffect(() => {
    if (!focusId || !requests || scrolled.current) return;
    const article = document.getElementById(requestElementId(focusId));
    if (!article) return;
    scrolled.current = true;
    article.scrollIntoView?.({ block: "start" });
  }, [focusId, requests]);

  function reload() {
    setLoads((count) => count + 1);
  }

  if (requests !== null && requests.length === 0 && !outcome && !error) return null;
  return (
    <section className="change-decide" aria-label="Change requests for this event">
      <h2>Change requests</h2>
      {outcome && <p className="request-notice" role="status">{outcome}</p>}
      {error && <div className="request-alert" role="alert">{error}</div>}
      {requests === null ? (
        <p className="request-empty">Loading change requests…</p>
      ) : (
        requests.map((request) => (
          <RequestToDecide
            key={request.id}
            request={request}
            eventStatus={event.status}
            onDecided={(message, decided) => {
              setError(null);
              setOutcome(message);
              onDecided(decided);
              reload();
            }}
            onRefused={(message) => {
              setOutcome(null);
              setError(message);
              reload();
            }}
          />
        ))
      )}
    </section>
  );
}

interface RequestToDecideProps {
  request: Review;
  eventStatus: string;
  onDecided: (message: string, decision: ChangeDecision) => void;
  onRefused: (message: string) => void;
}

// Also the Lead's panel (SCRUM-144), which has only the change request, not the event.
export function RequestToDecide({ request, eventStatus, onDecided, onRefused }: RequestToDecideProps) {
  const [step, setStep] = useState<"choose" | "approving" | "rejecting">("choose");
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const impact = request.significant ? impactParts(request.impact, eventStatus) : [];

  async function approve() {
    setBusy(true);
    try {
      const decided = await changeReviewApi.approve(request.id);
      onDecided(`Approved. The event is now ${statusWord(decided.event.status)}.`, decided);
    } catch (refusal) {
      onRefused(decisionErrorMessage(refusal));
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    const text = reason.trim();
    // AC 2: a reason, 1 to 1,000 characters, checked before anything is sent.
    if (!text) return setReasonError("Give a reason for rejecting.");
    if (text.length > REJECTION_MAX_LENGTH) return setReasonError("The reason must be at most 1,000 characters.");
    setBusy(true);
    try {
      const decided = await changeReviewApi.reject(request.id, text);
      onDecided("Rejected. The event keeps its current details.", decided);
    } catch (refusal) {
      onRefused(decisionErrorMessage(refusal));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="change-decide__request" id={requestElementId(request.id)} aria-label={`Change request from ${request.requested_by.name}`}>
      <p className="change-decide__who">
        <strong>{request.requested_by.name}</strong> asked {formatInstantDateTime(request.created_at)}
        {request.source === "coordinator" && " (a critical edit)"}
        {request.significant && <span className="change-badge change-badge--significant">Significant</span>}
      </p>
      <table className="change-table" aria-label="Requested changes">
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Current</th>
            <th scope="col">Proposed</th>
          </tr>
        </thead>
        <tbody>
          {request.changes.map((change) => (
            <tr key={change.field}>
              <td>{change.label || reviewLabel(change.field)}</td>
              <td>
                {reviewValue(change.field, change.current_value)}
                {change.stale && <span className="change-badge change-badge--stale">Changed since requested</span>}
              </td>
              <td>{reviewValue(change.field, change.new_value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {request.reason && <p>Reason: {request.reason}</p>}
      {impact.length > 0 && (
        <p className="change-decide__impact" role="note" aria-label="What approving does">
          <strong>What approving does:</strong> {impact.join(" · ")}
          {impact.at(-1)?.endsWith(".") ? "" : "."}
        </p>
      )}

      {step === "choose" && (
        <div className="request-form__actions">
          <button className="request-button request-button--quiet" type="button" onClick={() => setStep("rejecting")}>
            Reject
          </button>
          <button className="request-button request-button--primary" type="button" onClick={() => setStep("approving")}>
            Approve
          </button>
        </div>
      )}
      {step === "approving" && (
        <div className="change-decide__confirm">
          <p>Approve this change? The event takes the proposed values.</p>
          <div className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" disabled={busy} onClick={() => setStep("choose")}>
              Cancel
            </button>
            <button className="request-button request-button--primary" type="button" disabled={busy} onClick={() => void approve()}>
              {busy ? "Approving…" : "Approve change"}
            </button>
          </div>
        </div>
      )}
      {step === "rejecting" && (
        <div className="change-decide__confirm">
          <label className={`request-field request-field--wide${reasonError ? " request-field--invalid" : ""}`}>
            Reason for rejecting
            <textarea
              rows={3}
              value={reason}
              aria-invalid={reasonError !== null}
              aria-describedby={reasonError ? `reject-error-${request.id}` : undefined}
              onChange={(changed) => {
                setReason(changed.target.value);
                setReasonError(null);
              }}
            />
          </label>
          {reasonError && (
            <span className="venue-field-error" id={`reject-error-${request.id}`}>
              {reasonError}
            </span>
          )}
          <div className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" disabled={busy} onClick={() => setStep("choose")}>
              Cancel
            </button>
            <button className="request-button request-button--primary" type="button" disabled={busy} onClick={() => void reject()}>
              {busy ? "Rejecting…" : "Reject change"}
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
