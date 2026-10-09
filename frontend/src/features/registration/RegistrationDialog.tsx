import { useId, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { registrationErrorMessage } from "./api";
import { ConfirmationTicket } from "./ConfirmationTicket";
import { formatEventDate, formatEventTimeRange } from "./datetime";
import type { EventAvailability, RegistrationConfirmation } from "./types";

interface RegistrationDialogProps {
  event: EventAvailability;
  waitlisted: boolean;
  onRegister: (answers: Record<string, string>) => Promise<RegistrationConfirmation>;
  onClose: () => void;
}

/**
 * Register for an open event (SCRUM-26). The attendee is whoever X-Attendee-Id names, so the
 * form asks only the event's own registration questions. A full event has no action here yet:
 * joining its waitlist is SCRUM-52.
 */
export function RegistrationDialog({ event, waitlisted, onRegister, onClose }: RegistrationDialogProps) {
  const titleId = useId();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [confirmation, setConfirmation] = useState<RegistrationConfirmation | null>(null);

  const fieldLabels = Object.fromEntries(event.registrationFields.map((field) => [field.key, field.label]));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInvalidFields([]);
    setSubmitting(true);
    try {
      setConfirmation(await onRegister(answers));
    } catch (reason) {
      setError(registrationErrorMessage(reason, fieldLabels));
      if (reason instanceof ApiError) setInvalidFields(reason.fields);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        {confirmation ? (
          <ConfirmationTicket confirmation={confirmation} onDone={onClose} />
        ) : (
          <form className="reg-form" onSubmit={handleSubmit}>
            <button type="button" className="dialog__close" onClick={onClose} aria-label="Close">
              ×
            </button>

            <h3 id={titleId} className="reg-form__title">
              {event.title}
            </h3>
            <p className="reg-form__meta">
              {formatEventDate(event)}, {formatEventTimeRange(event)} ·{" "}
              {event.format === "online" ? "Online" : event.venue}
            </p>

            {waitlisted ? (
              <p className="reg-form__notice">You're on the waitlist for this event. Find it under My events.</p>
            ) : event.alreadyRegistered ? (
              <p className="reg-form__notice">You're already registered for this event. Find it under My events.</p>
            ) : event.isFull ? (
              <p className="reg-form__notice">This event is full.</p>
            ) : (
              <>
                {event.registrationFields.map((field) => (
                  <label key={field.key} className="reg-form__field">
                    {field.label}
                    {field.options ? (
                      <select
                        required={field.required}
                        value={answers[field.key] ?? ""}
                        aria-invalid={invalidFields.includes(field.key) || undefined}
                        onChange={(e) => setAnswers({ ...answers, [field.key]: e.target.value })}
                      >
                        <option value="">Choose…</option>
                        {field.options.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        required={field.required}
                        value={answers[field.key] ?? ""}
                        aria-invalid={invalidFields.includes(field.key) || undefined}
                        onChange={(e) => setAnswers({ ...answers, [field.key]: e.target.value })}
                      />
                    )}
                  </label>
                ))}

                {error && (
                  <p className="reg-form__error" role="alert">
                    {error}
                  </p>
                )}

                <button type="submit" className="button button--reserve reg-form__submit" disabled={submitting}>
                  {submitting ? "Reserving…" : "Reserve my seat"}
                </button>
              </>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
