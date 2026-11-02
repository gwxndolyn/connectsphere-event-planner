import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { formatInstantDateTime } from "../registration/datetime";
import type { EventRequest } from "../eventRequest/types";
import {
  REQUESTABLE,
  changeFieldErrors,
  changeFormValues,
  changeLabel,
  changeRequestApi,
  changeRequestErrorMessage,
  changeStatusLabel,
  changeValue,
  isPlanned,
  previewChanges,
  toChanges,
  type ChangeFormValues,
} from "./changeRequestApi";
import type { FieldChange, OrganiserChangeRequest } from "./types";
import "../eventRequest/eventRequests.css";
import "../venue/venues.css";
import "./changeRequests.css";

type Step = "closed" | "form" | "review";

/**
 * US29a (SCRUM-97): on the organiser's submitted request, ask for a change (AC 1), check each field's current and
 * proposed value with the reason before sending (AC 2, 3), and follow each request's status (AC 6). The event's
 * own values don't change (AC 4).
 */
export function EventChangeRequests({ event }: { event: EventRequest }) {
  const [requests, setRequests] = useState<OrganiserChangeRequest[] | null>(null);
  const [step, setStep] = useState<Step>("closed");
  const [initial, setInitial] = useState<ChangeFormValues>(() => changeFormValues(event));
  const [form, setForm] = useState<ChangeFormValues>(initial);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const requestable = REQUESTABLE.includes(event.status);
  const planned = isPlanned(event);

  useEffect(() => {
    let current = true;
    changeRequestApi
      .mine(event.id)
      .then((result) => {
        if (current) setRequests(result);
      })
      .catch((reason: unknown) => {
        if (current) {
          setRequests([]);
          setError(changeRequestErrorMessage(reason));
        }
      });
    return () => {
      current = false;
    };
  }, [event.id]);

  const changes = toChanges(event, initial, form);
  const preview: FieldChange[] = previewChanges(event, changes);

  function open() {
    const values = changeFormValues(event);
    setInitial(values);
    setForm(values);
    setReason("");
    setError(null);
    setFieldErrors({});
    setNotice(null);
    setStep("form");
  }

  function update(key: keyof ChangeFormValues, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    const linked = ["date", "startTime", "endTime", "preferred_start_time", "preferred_end_time"];
    const cleared = linked.includes(key) ? linked : [key];
    setFieldErrors((current) => Object.fromEntries(Object.entries(current).filter(([field]) => !cleared.includes(field))));
  }

  function review(submitted: FormEvent<HTMLFormElement>) {
    submitted.preventDefault();
    const missing: Record<string, string> = {};
    if (preview.length === 0) setError("Change at least one detail before reviewing.");
    if (!reason.trim()) missing.reason = "Give a reason for the change.";
    setFieldErrors(missing);
    if (preview.length === 0 || missing.reason) {
      if (preview.length > 0) setError("Give a reason for the change.");
      return;
    }
    setError(null);
    setStep("review");
  }

  async function send() {
    setSending(true);
    setError(null);
    try {
      const created = await changeRequestApi.create(event.id, changes, reason.trim());
      setRequests((current) => [created, ...(current ?? [])]);
      setStep("closed");
      setNotice("Change request sent. Your event keeps its current details until it's reviewed.");
    } catch (reason) {
      setFieldErrors(changeFieldErrors(reason));
      setError(changeRequestErrorMessage(reason));
      setStep("form");
    } finally {
      setSending(false);
    }
  }

  function field(label: string, key: keyof ChangeFormValues, control: (props: Record<string, unknown>) => ReactNode, wide = false) {
    const message = fieldErrors[key];
    const id = `change-${key}`;
    return (
      <div className={`request-field${wide ? " request-field--wide" : ""}${message ? " request-field--invalid" : ""}`}>
        <label htmlFor={id}>{label}</label>
        {control({
          id,
          value: form[key],
          "aria-invalid": message ? true : undefined,
          "aria-describedby": message ? `${id}-error` : undefined,
          onChange: (changed: { target: { value: string } }) => update(key, changed.target.value),
        })}
        {message && (
          <span id={`${id}-error`} className="venue-field-error">
            {message}
          </span>
        )}
      </div>
    );
  }

  return (
    <section className="change-requests" aria-labelledby="change-requests-title">
      <div className="change-requests__heading">
        <h2 id="change-requests-title">Change requests</h2>
        {requestable && step === "closed" && (
          <button type="button" className="request-button request-button--secondary" onClick={open}>
            Request a change
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
      {!requestable && <p className="request-empty">Changes can't be requested once an event is rejected, cancelled or completed.</p>}

      {step === "form" && (
        <form className="request-form" aria-label="Request a change" noValidate onSubmit={review}>
          <p className="change-requests__hint">Change only what you need. Your event keeps its current details until the change is reviewed.</p>
          <div className="venue-filters">
            {planned ? (
              <>
                {field("Date", "date", (props) => <input type="date" {...props} />)}
                {field("Start time", "startTime", (props) => <input type="time" {...props} />)}
                {field("End time", "endTime", (props) => <input type="time" {...props} />)}
              </>
            ) : (
              <>
                {field("Preferred date", "preferred_date", (props) => <input type="date" {...props} />)}
                {field("Preferred start time", "preferred_start_time", (props) => <input type="time" {...props} />)}
                {field("Preferred end time", "preferred_end_time", (props) => <input type="time" {...props} />)}
              </>
            )}
            {field("Expected attendees", "expected_attendees", (props) => <input inputMode="numeric" {...props} />)}
            {field("Room layout preference", "room_layout_preference", (props) => <input {...props} />)}
            {field("Event category", "event_category", (props) => <input {...props} />)}
            {field("Event name", "name", (props) => <input {...props} />, true)}
            {field("Accessibility needs", "accessibility_needs", (props) => <textarea rows={2} {...props} />, true)}
            {field("Equipment needs", "equipment_needs", (props) => <textarea rows={2} {...props} />, true)}
            {field("Purpose / description", "purpose", (props) => <textarea rows={3} {...props} />, true)}
          </div>
          <div className={`request-field request-field--wide${fieldErrors.reason ? " request-field--invalid" : ""}`}>
            <label htmlFor="change-reason">Reason for the change</label>
            <textarea
              id="change-reason"
              rows={3}
              value={reason}
              aria-invalid={fieldErrors.reason ? true : undefined}
              aria-describedby={fieldErrors.reason ? "change-reason-error" : undefined}
              onChange={(changed) => {
                setReason(changed.target.value);
                setFieldErrors(({ reason: _cleared, ...rest }) => rest);
              }}
            />
            {fieldErrors.reason && (
              <span id="change-reason-error" className="venue-field-error">
                {fieldErrors.reason}
              </span>
            )}
          </div>
          <div className="request-form__actions">
            <button type="button" className="request-button request-button--quiet" onClick={() => setStep("closed")}>
              Cancel
            </button>
            <button type="submit" className="request-button request-button--primary">
              Review change
            </button>
          </div>
        </form>
      )}

      {step === "review" && (
        <section className="change-review" aria-label="Review your change">
          <h3>Check your change before sending</h3>
          <ChangesTable changes={preview} label="Changes to send" />
          <p className="change-review__reason">
            <strong>Reason:</strong> {reason.trim()}
          </p>
          <div className="request-form__actions">
            <button type="button" className="request-button request-button--quiet" disabled={sending} onClick={() => setStep("form")}>
              Back to edit
            </button>
            <button type="button" className="request-button request-button--primary" disabled={sending} onClick={() => void send()}>
              {sending ? "Sending…" : "Send change request"}
            </button>
          </div>
        </section>
      )}

      {requests === null ? (
        <p className="request-empty">Loading change requests…</p>
      ) : requests.length === 0 ? (
        step === "closed" && <p className="request-empty">No change requests for this event yet.</p>
      ) : (
        <ul className="venue-booking-list" aria-label="Your change requests">
          {requests.map((request) => (
            <li key={request.id} className="venue-booking-row change-request-row">
              <div className="venue-booking-row__main">
                <span>Requested {formatInstantDateTime(request.created_at)}</span>
                <ChangesTable changes={request.changes} label="Requested changes" />
                {request.reason && <span>Reason: {request.reason}</span>}
                {/* US29b (SCRUM-143) AC 4: when it was decided, and why a rejection. */}
                {request.decided_at && <span>Decided {formatInstantDateTime(request.decided_at)}</span>}
                {request.rejection_reason && <span>Why it was rejected: {request.rejection_reason}</span>}
              </div>
              <span className={`venue-booking-status venue-booking-status--${request.status === "pending_approval" ? "requested" : request.status}`}>
                {changeStatusLabel(request.status)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ChangesTable({ changes, label }: { changes: FieldChange[]; label: string }) {
  return (
    <table className="change-table" aria-label={label}>
      <thead>
        <tr>
          <th scope="col">Field</th>
          <th scope="col">Current</th>
          <th scope="col">Proposed</th>
        </tr>
      </thead>
      <tbody>
        {changes.map((change) => (
          <tr key={change.field}>
            <td>{changeLabel(change.field)}</td>
            <td>{changeValue(change.field, change.old_value)}</td>
            <td>{changeValue(change.field, change.new_value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
