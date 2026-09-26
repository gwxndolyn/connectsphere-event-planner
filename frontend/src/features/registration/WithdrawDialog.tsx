import { useId, useState } from "react";
import { formatEventDate, formatEventTimeRange } from "./datetime";
import type { EventAvailability, Registration } from "./types";

interface WithdrawDialogProps {
  event: EventAvailability;
  registration: Registration;
  waitlistPosition?: number;
  onConfirm: () => void;
  onClose: () => void;
}

const timeFormatter = new Intl.DateTimeFormat("en-SG", { hour: "numeric", minute: "2-digit" });

/**
 * Withdrawing is destructive — on a full event the seat goes straight to whoever is next,
 * and coming back means rejoining at the end of the queue. So it takes two steps: say what
 * will happen, then confirm it happened (SCRUM-38; D5 settles that "sees a confirmation"
 * means on-screen, not email).
 *
 * Mockup only: this drives the in-browser registry, not the API (§7).
 */
export function WithdrawDialog({
  event,
  registration,
  waitlistPosition,
  onConfirm,
  onClose,
}: WithdrawDialogProps) {
  const titleId = useId();
  const [withdrawnAt, setWithdrawnAt] = useState<Date | null>(null);
  const isWaitlisted = registration.status === "waitlisted";

  function handleConfirm() {
    setWithdrawnAt(new Date());
    onConfirm();
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="dialog__close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {withdrawnAt ? (
          <div className="ticket">
            <div className="ticket__icon ticket__icon--withdrawn" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="24" height="24">
                <path
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  d="M7 12h10"
                />
              </svg>
            </div>

            <h3 id={titleId} className="ticket__title">
              {isWaitlisted ? "You've left the waitlist" : "Withdrawal confirmed"}
            </h3>
            <p className="ticket__event">{event.title}</p>

            <div className="ticket__details">
              <p>Withdrawn at {timeFormatter.format(withdrawnAt)}</p>
              <p>
                {formatEventDate(event)}, {formatEventTimeRange(event)}
              </p>
            </div>

            <p className="ticket__message">
              {isWaitlisted
                ? "You're no longer in the queue for this event. Everyone behind you moves up one place."
                : "Your seat has been released. If anyone is on the waitlist, it goes to the next person in line."}
            </p>

            <button
              type="button"
              className="button button--secondary ticket__done"
              onClick={onClose}
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <h3 id={titleId} className="reg-form__title">
              {isWaitlisted ? "Leave this waitlist?" : "Withdraw from this event?"}
            </h3>
            <p className="reg-form__meta">
              {event.title} · {formatEventDate(event)}, {formatEventTimeRange(event)}
            </p>

            <p className="reg-form__notice">
              {isWaitlisted
                ? `You'll lose ${waitlistPosition ? `position ${waitlistPosition}` : "your place"} in the queue. Rejoining later puts you at the back.`
                : "Your seat will be offered to the next person on the waitlist. If nobody is waiting, it goes back into general registration."}
            </p>

            <p className="withdraw__hint">You can do this any time before the event starts.</p>

            <div className="withdraw__actions">
              <button type="button" className="button button--secondary" onClick={onClose}>
                {isWaitlisted ? "Stay on the waitlist" : "Keep my seat"}
              </button>
              <button type="button" className="button button--danger" onClick={handleConfirm}>
                {isWaitlisted ? "Leave waitlist" : "Withdraw"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
