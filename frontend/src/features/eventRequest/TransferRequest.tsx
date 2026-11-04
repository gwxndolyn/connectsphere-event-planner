import { useState } from "react";
import { ApiError, apiClient } from "../../api/client";
import { statusLabel } from "./clarificationSections";
import "./eventRequests.css";
import "../cancellation/cancellation.css";

// The statuses a Lead can move an event in (REASSIGNABLE_STATUSES); the API refuses a transfer request outside them.
const TRANSFERABLE = ["under_review", "awaiting_clarification", "approved", "planning", "confirmed", "preparation"];

const REASON_MAX_LENGTH = 1000;
const FALLBACK_MESSAGE = "The request could not be completed. Check the backend connection and try again.";

function transferErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  switch (error.code) {
    case "MISSING_REQUIRED_FIELD":
      return "Give a reason, of at most 1,000 characters.";
    case "REASSIGNMENT_NOT_ALLOWED": {
      const status = typeof error.body.status === "string" ? statusLabel(error.body.status) : null;
      return status ? `A transfer can't be requested while the event is ${status}.` : "A transfer can't be requested for this event now.";
    }
    case "NOT_FOUND":
      return "This event isn't assigned to you any more, so you can't ask to transfer it.";
    case "FORBIDDEN":
      return "Transfer requests are for the event's coordinator.";
    default:
      return FALLBACK_MESSAGE;
  }
}

interface TransferRequestProps {
  eventId: string;
  status: string;
}

/**
 * US10e AC 6 (SCRUM-146): the event's assigned coordinator asks the Coordinator Leads to move it to someone else,
 * with a reason. Nothing moves: every active Lead is told, and one may reassign it (SCRUM-83). The page shows this
 * only to the event's assigned coordinator; it shows nothing outside TRANSFERABLE.
 */
export function TransferRequest({ eventId, status }: TransferRequestProps) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reasonInvalid, setReasonInvalid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [sending, setSending] = useState(false);

  if (!TRANSFERABLE.includes(status)) return null;

  function start() {
    setOpen(true);
    setReason("");
    setReasonInvalid(false);
    setError(null);
    setSent(false);
  }

  async function send() {
    if (!reason.trim()) {
      setReasonInvalid(true);
      setError(transferErrorMessage(new ApiError(422, "MISSING_REQUIRED_FIELD", ["reason"])));
      return;
    }
    setSending(true);
    setError(null);
    try {
      await apiClient.post(`/api/v1/event-requests/${eventId}/transfer-request`, { reason: reason.trim() });
      setOpen(false);
      setReason("");
      setSent(true);
    } catch (failure) {
      setError(transferErrorMessage(failure));
      if (failure instanceof ApiError && failure.fields.includes("reason")) setReasonInvalid(true);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="event-cancellation" aria-labelledby={`transfer-title-${eventId}`}>
      <div className="event-cancellation__heading">
        <h2 id={`transfer-title-${eventId}`}>Transfer</h2>
        {!open && (
          <button type="button" className="request-button request-button--secondary" onClick={start}>
            Request a transfer
          </button>
        )}
      </div>

      {sent && (
        <p className="request-notice" role="status">
          Transfer requested. The Coordinator Leads have been told.
        </p>
      )}

      {open && (
        <div className="event-cancellation__form">
          <p className="event-cancellation__hint">
            The Coordinator Leads decide whether to move this event to another coordinator. Until then it stays with you.
          </p>
          {error && (
            <div className="request-alert" role="alert">
              {error}
            </div>
          )}
          <div className={`request-field request-field--wide${reasonInvalid ? " request-field--invalid" : ""}`}>
            <label htmlFor={`transfer-reason-${eventId}`}>Reason for the transfer</label>
            <textarea
              id={`transfer-reason-${eventId}`}
              rows={3}
              maxLength={REASON_MAX_LENGTH}
              value={reason}
              aria-invalid={reasonInvalid || undefined}
              onChange={(change) => {
                setReason(change.target.value);
                setReasonInvalid(false);
              }}
            />
          </div>
          <div className="request-form__actions">
            <button type="button" className="request-button request-button--quiet" disabled={sending} onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button type="button" className="request-button request-button--primary" disabled={sending} onClick={() => void send()}>
              {sending ? "Sending…" : "Send"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
