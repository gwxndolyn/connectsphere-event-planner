import { useId, useState, type FormEvent } from "react";
import { ConfirmationTicket } from "./ConfirmationTicket";
import { formatEventDate, formatEventTimeRange } from "./datetime";
import type { Attendee, EventAvailability, RegistrationResult } from "./types";

interface RegistrationDialogProps {
  event: EventAvailability;
  currentAttendee: Attendee | null;
  onRegister: (name: string, email: string) => RegistrationResult;
  onJoinWaitlist: (email: string) => RegistrationResult;
  onClose: () => void;
}

export function RegistrationDialog({
  event,
  currentAttendee,
  onRegister,
  onJoinWaitlist,
  onClose,
}: RegistrationDialogProps) {
  const titleId = useId();
  const isFull = event.registeredCount >= event.capacity;

  const [name, setName] = useState(currentAttendee?.name ?? "");
  const [email, setEmail] = useState(currentAttendee?.email ?? "");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RegistrationResult | null>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const outcome = isFull ? onJoinWaitlist(email) : onRegister(name, email);

    if (outcome.status === "duplicate") {
      setError(
        isFull
          ? "You're already on the list for this event."
          : "You're already registered for this event.",
      );
      return;
    }

    setResult(outcome);
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        {result ? (
          <ConfirmationTicket
            event={event}
            variant={result.status === "registered" ? "registered" : "waitlisted"}
            attendeeName={result.status === "registered" ? name : undefined}
            email={email}
            confirmationCode={result.status === "registered" ? result.confirmationCode : undefined}
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

            {isFull && (
              <p className="reg-form__notice">
                This event is full. Join the waitlist and we'll email you if a seat opens up.
              </p>
            )}

            {!isFull && (
              <label className="reg-form__field">
                Name
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                />
              </label>
            )}

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

            {error && <p className="reg-form__error">{error}</p>}

            <button type="submit" className="button button--reserve reg-form__submit">
              {isFull ? "Join the waitlist" : "Reserve my seat"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
