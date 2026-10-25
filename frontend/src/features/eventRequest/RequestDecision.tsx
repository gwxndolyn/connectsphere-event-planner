import { useState } from "react";
import { ApiError, apiClient } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import type { EventRequest } from "./types";

function decisionError(error: unknown): string {
  if (!(error instanceof ApiError)) return "The decision could not be saved. Check the backend connection and try again.";
  switch (error.code) {
    case "MISSING_REQUIRED_FIELD":
      return "Give the organiser a reason for rejecting this request.";
    case "REQUEST_NOT_DECIDABLE":
      return "This request can only be approved or rejected while it's under review.";
    case "SELF_DECISION_NOT_ALLOWED":
      return "You can't decide a request you created.";
    case "NOT_FOUND":
      return "This request isn't assigned to you, so you can't decide it.";
    default:
      return `The backend rejected the decision (${error.status}).`;
  }
}

interface RequestDecisionPanelProps {
  request: EventRequest;
  onDecided: (request: EventRequest) => void;
}

/** US17 (SCRUM-84): the assigned coordinator approves, or rejects with a reason (AC 1–3). */
export function RequestDecisionPanel({ request, onDecided }: RequestDecisionPanelProps) {
  const [rejecting, setRejecting] = useState(false);
  const [reasonText, setReasonText] = useState("");
  const [reasonInvalid, setReasonInvalid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function decide(action: "approve" | "reject") {
    if (action === "reject" && !reasonText.trim()) {
      setReasonInvalid(true);
      setError(decisionError(new ApiError(422, "MISSING_REQUIRED_FIELD", ["reason"])));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const decided = await apiClient.post<EventRequest>(
        `/api/v1/event-requests/${request.id}/${action}`,
        action === "reject" ? { reason: reasonText } : {},
      );
      onDecided(decided);
    } catch (failure) {
      setError(decisionError(failure));
      if (failure instanceof ApiError && failure.fields.includes("reason")) setReasonInvalid(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="request-decision" aria-labelledby="request-decision-title">
      <h2 id="request-decision-title">Decision</h2>
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {rejecting ? (
        <>
          <label className={`request-field request-field--wide${reasonInvalid ? " request-field--invalid" : ""}`}>
            Reason for rejecting
            <textarea
              aria-invalid={reasonInvalid}
              rows={3}
              maxLength={1000}
              value={reasonText}
              onChange={(change) => {
                setReasonText(change.target.value);
                setReasonInvalid(false);
              }}
            />
          </label>
          <div className="request-form__actions">
            <button className="request-button request-button--quiet" type="button" onClick={() => setRejecting(false)}>
              Cancel
            </button>
            <button className="request-button request-button--primary" type="button" disabled={saving} onClick={() => void decide("reject")}>
              {saving ? "Rejecting…" : "Confirm rejection"}
            </button>
          </div>
        </>
      ) : (
        <div className="request-form__actions">
          <button className="request-button request-button--secondary" type="button" disabled={saving} onClick={() => setRejecting(true)}>
            Reject request
          </button>
          <button className="request-button request-button--primary" type="button" disabled={saving} onClick={() => void decide("approve")}>
            {saving ? "Approving…" : "Approve request"}
          </button>
        </div>
      )}
    </section>
  );
}

/** The recorded decision (AC 5): who, when, and why for a rejection. Nothing before a decision. */
export function DecisionOutcome({ request }: { request: EventRequest }) {
  if (!request.decided_at) return null;
  const rejected = request.status === "rejected";
  return (
    <div className="request-outcome" role="status" aria-label="Decision">
      <strong>{rejected ? "Rejected" : "Approved"}</strong>
      {request.decided_by ? ` by ${request.decided_by.name}` : ""} on {formatInstantDateTime(request.decided_at)}
      {rejected && request.rejection_reason && <p className="request-outcome__reason">Reason: {request.rejection_reason}</p>}
    </div>
  );
}
