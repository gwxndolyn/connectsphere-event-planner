import { useEffect, useState } from "react";
import { ApiError, apiClient } from "../../api/client";
import { areaLabel, checklistLabel } from "../safety/checklist";
import type { SafetyStatus } from "../safety/types";
import { formatInstantDateTime } from "../registration/datetime";
import type { EventRequest } from "./types";
import "../safety/safety.css";

// The statuses a safety review applies to: from Approved, until the event is over.
const REVIEWED = new Set(["approved", "planning", "confirmed", "preparation"]);

function sendError(error: unknown): string {
  if (!(error instanceof ApiError)) return "The request could not be completed. Check the backend connection and try again.";
  if (error.code === "SAFETY_REVIEW_NOT_ALLOWED") return "This arrangement can't be sent for another review right now.";
  if (error.code === "NOT_FOUND") return "This event isn't assigned to you.";
  return `The backend rejected the request (${error.status}).`;
}

interface SafetyOutcomeProps {
  request: EventRequest;
  // The assigned coordinator may send a rejected arrangement back, or mark requested changes done, for another
  // review (US30a AC 4, US30b AC 4).
  canResend?: boolean;
  // Called after it is sent back, so the readiness list reads the new state.
  onResent?: () => void;
}

/**
 * US30a (SCRUM-99): the safety outcome and its comments for the Organiser (AC 7) and the Coordinator
 * (AC 4), never the Safety Officer's internal notes: the API doesn't send them.
 */
export function SafetyOutcome({ request, canResend = false, onResent }: SafetyOutcomeProps) {
  const [status, setStatus] = useState<SafetyStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const applies = REVIEWED.has(request.status);

  useEffect(() => {
    if (!applies) return;
    let current = true;
    apiClient
      .get<SafetyStatus>(`/api/v1/event-requests/${request.id}/safety-reviews`)
      .then((result) => {
        if (current) setStatus(result);
      })
      .catch(() => {
        // The outcome is extra to the screen it sits on: without it the screen still works.
      });
    return () => {
      current = false;
    };
  }, [applies, request.id, request.status]);

  async function resend() {
    setSending(true);
    setError(null);
    try {
      setStatus(await apiClient.post<SafetyStatus>(`/api/v1/event-requests/${request.id}/safety-review-request`, {}));
      onResent?.();
    } catch (reason) {
      setError(sendError(reason));
    } finally {
      setSending(false);
    }
  }

  if (!applies || status === null) return null;
  const latest = status.reviews[0];
  const issues = latest ? Object.entries(latest.checklist).filter(([, given]) => given.result === "issue") : [];

  return (
    <section className="safety-outcome" aria-label="Safety review">
      {error && <div className="request-alert" role="alert">{error}</div>}
      {status.state === "approved" && latest && (
        <p>
          <strong>Safety approved</strong> by {latest.reviewer.name} on {formatInstantDateTime(latest.created_at)}.
          {latest.comments ? ` ${latest.comments}` : ""}
        </p>
      )}
      {status.state === "rejected" && latest && (
        <>
          <p>
            <strong>Safety arrangement rejected</strong> by {latest.reviewer.name} on {formatInstantDateTime(latest.created_at)}.
            The event stays in {request.status.replaceAll("_", " ")}; the venue arrangement needs revising.
          </p>
          <p>Comments: {latest.comments}</p>
          {issues.length > 0 && (
            <ul className="safety-outcome__issues" aria-label="Issues found">
              {issues.map(([key, given]) => (
                <li key={key}>
                  {checklistLabel(key)}
                  {given.comment ? `: ${given.comment}` : ""}
                </li>
              ))}
            </ul>
          )}
          {canResend && (
            <div className="request-form__actions">
              <button className="request-button request-button--primary" type="button" disabled={sending} onClick={() => void resend()}>
                {sending ? "Sending…" : "Send for another review"}
              </button>
            </div>
          )}
        </>
      )}
      {status.state === "changes_requested" && latest && (
        <>
          <p>
            <strong>Changes requested</strong> by {latest.reviewer.name} on {formatInstantDateTime(latest.created_at)}.
            The event stays in {request.status.replaceAll("_", " ")} with these areas marked for review; nothing else is reset.
          </p>
          <ul className="safety-outcome__issues" aria-label="Areas to review">
            {(latest.areas ?? []).map((key) => (
              <li key={key}>{areaLabel(key)}</li>
            ))}
          </ul>
          <p>Comments: {latest.comments}</p>
          {issues.length > 0 && (
            <ul className="safety-outcome__issues" aria-label="Issues found">
              {issues.map(([key, given]) => (
                <li key={key}>
                  {checklistLabel(key)}
                  {given.comment ? `: ${given.comment}` : ""}
                </li>
              ))}
            </ul>
          )}
          {canResend && (
            <div className="request-form__actions">
              <button className="request-button request-button--primary" type="button" disabled={sending} onClick={() => void resend()}>
                {sending ? "Sending…" : "Mark changes done"}
              </button>
            </div>
          )}
        </>
      )}
      {status.state === "pending" && (
        <p>{latest ? "Sent for another safety review." : "Waiting for the Safety Officer's review."}</p>
      )}
    </section>
  );
}
