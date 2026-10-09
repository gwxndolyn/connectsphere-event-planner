import { useId, useState } from "react";
import { registrationErrorMessage } from "./api";
import { formatEventDate, formatEventTimeRange, formatInstantTime, toTimed } from "./datetime";
import type { MyRegistration, WithdrawalResult } from "./types";

interface WithdrawDialogProps {
  registration: MyRegistration;
  onConfirm: () => Promise<WithdrawalResult>;
  onClose: () => void;
}

/**
 * Withdrawing is destructive — on a full event the seat goes straight to whoever is next,
 * and coming back means rejoining at the end of the queue. So it takes two steps: say what
 * will happen, then confirm it happened (SCRUM-38; D5 settles that "sees a confirmation"
 * means on-screen, not email). The confirmation shows only once the API has accepted it.
 */
export function WithdrawDialog({ registration, onConfirm, onClose }: WithdrawDialogProps) {
  const titleId = useId();
  const [result, setResult] = useState<WithdrawalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isWaitlisted = registration.status === "waitlisted";
  const timed = toTimed(registration.date, registration.startTime, registration.endTime);

  async function handleConfirm() {
    setError(null);
    setSubmitting(true);
    try {
      setResult(await onConfirm());
    } catch (reason) {
      setError(registrationErrorMessage(reason));
    } finally {
      setSubmitting(false);
    }
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

        {result ? (
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
            <p className="ticket__event">{result.eventTitle}</p>

            <div className="ticket__details">
              <p>Withdrawn at {formatInstantTime(result.withdrawnAt)}</p>
              <p>
                {formatEventDate(timed)}, {formatEventTimeRange(timed)}
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
              {registration.eventTitle} · {formatEventDate(timed)}, {formatEventTimeRange(timed)}
            </p>

            <p className="reg-form__notice">
              {isWaitlisted
                ? `You'll lose ${registration.waitlistPosition ? `position ${registration.waitlistPosition}` : "your place"} in the queue. Rejoining later puts you at the back.`
                : "Your seat will be offered to the next person on the waitlist. If nobody is waiting, it goes back into general registration."}
            </p>

            <p className="withdraw__hint">You can do this any time before the event starts.</p>

            {error && (
              <p className="reg-form__error" role="alert">
                {error}
              </p>
            )}

            <div className="withdraw__actions">
              <button type="button" className="button button--secondary" onClick={onClose}>
                {isWaitlisted ? "Stay on the waitlist" : "Keep my seat"}
              </button>
              <button
                type="button"
                className="button button--danger"
                onClick={handleConfirm}
                disabled={submitting}
              >
                {isWaitlisted ? "Leave waitlist" : "Withdraw"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
