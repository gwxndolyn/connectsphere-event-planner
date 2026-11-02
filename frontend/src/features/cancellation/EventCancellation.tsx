import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { formatInstantDateTime } from "../registration/datetime";
import type { EventRequest, EventRequestStatus } from "../eventRequest/types";
import {
  CANCELLABLE,
  REASON_MAX_LENGTH,
  cancellationApi,
  cancellationErrorMessage,
  cancellationStatusLabel,
} from "./cancellationApi";
import type { Cancellation } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";
import "./cancellation.css";

// What the open form is for: the organiser asking, the coordinator rejecting a request or cancelling directly.
type Step = "closed" | "ask" | "reject" | "cancel" | "confirm-cancel" | "confirm-approve";

interface EventCancellationProps {
  event: EventRequest;
  role: "organiser" | "coordinator";
  // The event's status after a change: the page updates `event`, which this panel reads its status from.
  onChanged: (status: EventRequestStatus) => void;
}

/**
 * US9 (SCRUM-12): the organiser asks to cancel their event with a reason (AC 1); the assigned coordinator approves
 * or rejects the request (AC 2), or cancels the event directly after confirming (AC 3, 4). Both see the record:
 * who asked, why and when, and who decided and when (AC 8).
 */
export function EventCancellation({ event, role, onChanged }: EventCancellationProps) {
  const [records, setRecords] = useState<Cancellation[] | null>(null);
  // The history couldn't be loaded, so whether a request is waiting is unknown: no actions are offered.
  const [loadFailed, setLoadFailed] = useState(false);
  const [step, setStep] = useState<Step>("closed");
  const [reason, setReason] = useState("");
  const [reasonInvalid, setReasonInvalid] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const status = event.status;

  useEffect(() => {
    let current = true;
    cancellationApi
      .list(event.id)
      .then((result) => {
        if (current) setRecords(result);
      })
      .catch((failure: unknown) => {
        if (current) {
          setLoadFailed(true);
          setError(cancellationErrorMessage(failure));
        }
      });
    return () => {
      current = false;
    };
  }, [event.id]);

  const pending = records?.find((record) => record.status === "pending") ?? null;
  const cancellable = CANCELLABLE.includes(status);

  function open(next: Step) {
    setStep(next);
    setReason("");
    setReasonInvalid(false);
    setError(null);
    setNotice(null);
  }

  function needsReason(): boolean {
    if (reason.trim()) return false;
    setReasonInvalid(true);
    setError("Give a reason, of at most 1,000 characters.");
    return true;
  }

  async function run(action: () => Promise<Cancellation>, done: string) {
    setSaving(true);
    setError(null);
    try {
      const result = await action();
      setRecords((current) => [result, ...(current ?? []).filter((record) => record.id !== result.id)]);
      setStep("closed");
      setReason("");
      setNotice(done);
      onChanged(result.event_status);
    } catch (failure) {
      setError(cancellationErrorMessage(failure));
      if (failure instanceof ApiError && failure.fields.includes("reason")) setReasonInvalid(true);
    } finally {
      setSaving(false);
    }
  }

  function reasonField(label: string) {
    return (
      <div className={`request-field request-field--wide${reasonInvalid ? " request-field--invalid" : ""}`}>
        <label htmlFor="cancellation-reason">{label}</label>
        <textarea
          id="cancellation-reason"
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
    );
  }

  function actions(back: string, submit: string, busy: string, onSubmit: () => void, danger = false) {
    return (
      <div className="request-form__actions">
        <button type="button" className="request-button request-button--quiet" disabled={saving} onClick={() => setStep("closed")}>
          {back}
        </button>
        <button
          type="button"
          className={`request-button ${danger ? "request-button--danger" : "request-button--primary"}`}
          disabled={saving}
          onClick={onSubmit}
        >
          {saving ? busy : submit}
        </button>
      </div>
    );
  }

  return (
    <section className="event-cancellation" aria-labelledby="event-cancellation-title">
      <div className="event-cancellation__heading">
        <h2 id="event-cancellation-title">Cancellation</h2>
        {step === "closed" && role === "organiser" && cancellable && !pending && records !== null && (
          <button type="button" className="request-button request-button--secondary" onClick={() => open("ask")}>
            Request cancellation
          </button>
        )}
        {step === "closed" && role === "coordinator" && cancellable && !pending && records !== null && (
          <button type="button" className="request-button request-button--secondary" onClick={() => open("cancel")}>
            Cancel event
          </button>
        )}
      </div>

      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <p className="request-notice" role="status">
          {notice}
        </p>
      )}
      {status === "cancelled" && <p className="event-cancellation__banner">This event is cancelled.</p>}

      {step === "ask" && (
        <div className="event-cancellation__form">
          <p className="event-cancellation__hint">
            Your coordinator decides whether to cancel. Until then the event goes ahead as planned. If it's cancelled,
            everyone registered or waiting is told, with your reason.
          </p>
          {reasonField("Reason for cancelling")}
          {actions("Back", "Send cancellation request", "Sending…", () => {
            if (!needsReason()) void run(() => cancellationApi.request(event.id, reason.trim()), "Cancellation request sent.");
          })}
        </div>
      )}

      {step === "cancel" && (
        <div className="event-cancellation__form">
          {reasonField("Reason for cancelling")}
          {actions("Back", "Continue", "Continue", () => {
            if (!needsReason()) setStep("confirm-cancel");
          })}
        </div>
      )}

      {step === "confirm-cancel" && (
        <div className="event-cancellation__form event-cancellation__confirm" role="group" aria-label="Confirm cancellation">
          <h3>Cancel {event.name || "this event"}?</h3>
          <p>
            Its venue bookings and reserved equipment are released, and the organiser, everyone registered or waiting,
            and any venue or technical support staff involved are told, with your reason.{" "}
            <strong>This can't be undone.</strong>
          </p>
          <p className="change-review__reason">
            <strong>Reason:</strong> {reason.trim()}
          </p>
          {actions("Back", "Cancel event", "Cancelling…", () => {
            void run(() => cancellationApi.cancel(event.id, reason.trim()), "The event is cancelled.");
          }, true)}
        </div>
      )}

      {pending && role === "coordinator" && step !== "reject" && step !== "confirm-approve" && (
        <div className="event-cancellation__pending">
          <p>
            <strong>{pending.requested_by.name}</strong> asked to cancel this event: {pending.reason}
          </p>
          <div className="request-form__actions">
            <button type="button" className="request-button request-button--secondary" disabled={saving} onClick={() => open("reject")}>
              Reject cancellation
            </button>
            <button
              type="button"
              className="request-button request-button--danger"
              disabled={saving}
              onClick={() => open("confirm-approve")}
            >
              Approve cancellation
            </button>
          </div>
        </div>
      )}

      {/* As Cancel event's: approving releases the same things and can't be undone either (PR #119 review). */}
      {pending && step === "confirm-approve" && (
        <div className="event-cancellation__form event-cancellation__confirm" role="group" aria-label="Confirm cancellation">
          <h3>Cancel {event.name || "this event"}?</h3>
          <p>
            Approving {pending.requested_by.name}'s request cancels the event: its venue bookings and reserved equipment
            are released, and the organiser, everyone registered or waiting, and any venue or technical support staff
            involved are told, with their reason. <strong>This can't be undone.</strong>
          </p>
          <p className="change-review__reason">
            <strong>Reason:</strong> {pending.reason}
          </p>
          {actions("Back", "Approve cancellation", "Cancelling…", () => {
            void run(() => cancellationApi.approve(pending.id), "The event is cancelled.");
          }, true)}
        </div>
      )}

      {pending && step === "reject" && (
        <div className="event-cancellation__form">
          {reasonField("Reason for rejecting")}
          {actions("Back", "Reject cancellation", "Rejecting…", () => {
            if (!needsReason()) void run(() => cancellationApi.reject(pending.id, reason.trim()), "Cancellation request rejected.");
          })}
        </div>
      )}

      {pending && role === "organiser" && (
        <p className="event-cancellation__hint">Your cancellation request is waiting for your coordinator's decision.</p>
      )}

      {loadFailed ? null : records === null ? (
        <p className="request-empty">Loading cancellation history…</p>
      ) : records.length === 0 ? (
        step === "closed" && <p className="request-empty">No cancellation requests for this event.</p>
      ) : (
        <ul className="venue-booking-list" aria-label="Cancellation history">
          {records.map((record) => (
            <li key={record.id} className="venue-booking-row">
              <div className="venue-booking-row__main">
                <span>
                  {record.direct ? "Cancelled" : "Requested"} by {record.requested_by.name} on{" "}
                  {formatInstantDateTime(record.requested_at)}
                </span>
                <span>Reason: {record.reason}</span>
                {record.decided_by && record.decided_at && !record.direct && (
                  <span>
                    {record.status === "approved" ? "Approved" : "Rejected"} by {record.decided_by.name} on{" "}
                    {formatInstantDateTime(record.decided_at)}
                  </span>
                )}
                {record.rejection_reason && <span>Why it was rejected: {record.rejection_reason}</span>}
              </div>
              <span className={`venue-booking-status cancellation-status--${record.status}`}>
                {cancellationStatusLabel(record.status)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
