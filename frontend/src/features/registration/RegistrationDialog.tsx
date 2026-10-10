import { useId, useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { registrationErrorMessage } from "./api";
import { ConfirmationTicket } from "./ConfirmationTicket";
import { formatEventDate, formatEventTimeRange } from "./datetime";
import type { EventAvailability, RegistrationConfirmation, WaitlistConfirmation } from "./types";

interface RegistrationDialogProps {
  event: EventAvailability;
  waitlisted: boolean;
  onRegister: (answers: Record<string, string>) => Promise<RegistrationConfirmation>;
  onJoinWaitlist: (email: string) => Promise<WaitlistConfirmation>;
  onRefresh: () => Promise<void>;
  onClose: () => void;
}

type Outcome =
  | { kind: "registered"; confirmation: RegistrationConfirmation }
  | { kind: "waitlisted"; confirmation: WaitlistConfirmation };

/**
 * Register for an open event (SCRUM-26), or join the waitlist of a full one that has one (US6a,
 * SCRUM-52). Registering identifies the attendee by X-Attendee-Id, so it asks only the event's own
 * questions; joining a waitlist takes an email (D7), which links the place to the attendee's
 * My events when it matches their account (D3).
 */
export function RegistrationDialog({
  event,
  waitlisted,
  onRegister,
  onJoinWaitlist,
  onRefresh,
  onClose,
}: RegistrationDialogProps) {
  const titleId = useId();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [invalidFields, setInvalidFields] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  // The event filled up while the dialog was open, and EVENT_FULL said a waitlist is offered.
  const [filledWhileOpen, setFilledWhileOpen] = useState(false);

  const canJoinWaitlist = (event.isFull && event.waitlistAvailable) || filledWhileOpen;
  const fieldLabels = Object.fromEntries(event.registrationFields.map((field) => [field.key, field.label]));

  async function handleRegister() {
    try {
      setOutcome({ kind: "registered", confirmation: await onRegister(answers) });
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "EVENT_FULL" && reason.body.waitlist_available === true) {
        setFilledWhileOpen(true);
        void onRefresh();
        return;
      }
      setError(registrationErrorMessage(reason, fieldLabels));
      if (reason instanceof ApiError) setInvalidFields(reason.fields);
    }
  }

  async function handleJoinWaitlist() {
    try {
      setOutcome({ kind: "waitlisted", confirmation: await onJoinWaitlist(email.trim()) });
    } catch (reason) {
      if (reason instanceof ApiError && reason.code === "SEATS_AVAILABLE") {
        // A seat came free: back to the register form once the board has the new count.
        setFilledWhileOpen(false);
        void onRefresh();
      }
      setError(
        reason instanceof ApiError && reason.code === "ALREADY_REGISTERED"
          ? "That email is already registered or on the waitlist for this event."
          : registrationErrorMessage(reason),
      );
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInvalidFields([]);
    setSubmitting(true);
    try {
      await (canJoinWaitlist ? handleJoinWaitlist() : handleRegister());
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
        {outcome?.kind === "registered" ? (
          <ConfirmationTicket
            variant="registered"
            event={outcome.confirmation.event}
            registrationId={outcome.confirmation.registrationId}
            onDone={onClose}
          />
        ) : outcome?.kind === "waitlisted" ? (
          <ConfirmationTicket
            variant="waitlisted"
            event={event}
            position={outcome.confirmation.position}
            onDone={onClose}
          />
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
            ) : canJoinWaitlist ? (
              <>
                <p className="reg-form__notice">
                  This event is full. Join the waitlist and you'll be offered a seat if one opens up.
                </p>

                <label className="reg-form__field">
                  Email
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                  />
                </label>
                <p className="reg-form__hint">Use the email you registered with, so the place shows under My events.</p>

                {error && (
                  <p className="reg-form__error" role="alert">
                    {error}
                  </p>
                )}

                <button type="submit" className="button button--reserve reg-form__submit" disabled={submitting}>
                  {submitting ? "Joining…" : "Join the waitlist"}
                </button>
              </>
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
