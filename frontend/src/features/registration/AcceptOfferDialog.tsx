import { useId, useState } from "react";
import { registrationErrorMessage } from "./api";
import { ConfirmationTicket } from "./ConfirmationTicket";
import { formatEventDate, formatEventTimeRange, formatInstantDateTime, toTimed } from "./datetime";
import type { MyRegistration, RegistrationConfirmation } from "./types";

interface AcceptOfferDialogProps {
  registration: MyRegistration;
  onConfirm: () => Promise<RegistrationConfirmation>;
  onClose: () => void;
}

/**
 * US6b AC 2 (SCRUM-76): a place freed by a withdrawal is held for this attendee until the offer
 * expires. Accepting turns the waitlist place into a confirmed registration, so it ends on the
 * same ticket as registering. The ticket shows only once the API has accepted it.
 */
export function AcceptOfferDialog({ registration, onConfirm, onClose }: AcceptOfferDialogProps) {
  const titleId = useId();
  const [confirmation, setConfirmation] = useState<RegistrationConfirmation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const timed = toTimed(registration.date, registration.startTime, registration.endTime);

  async function handleConfirm() {
    setError(null);
    setSubmitting(true);
    try {
      setConfirmation(await onConfirm());
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
        {confirmation ? (
          <ConfirmationTicket
            variant="registered"
            event={confirmation.event}
            registrationId={confirmation.registrationId}
            onDone={onClose}
            doneLabel="Done"
          />
        ) : (
          <>
            <button type="button" className="dialog__close" onClick={onClose} aria-label="Close">
              ×
            </button>
            <h3 id={titleId} className="reg-form__title">
              Take your place?
            </h3>
            <p className="reg-form__meta">
              {registration.eventTitle} · {formatEventDate(timed)}, {formatEventTimeRange(timed)}
            </p>

            <p className="reg-form__notice">
              A seat opened up and is held for you
              {registration.offerExpiresAt ? ` until ${formatInstantDateTime(registration.offerExpiresAt)}` : ""}. After
              that it goes to the next person on the waitlist.
            </p>

            {error && (
              <p className="reg-form__error" role="alert">
                {error}
              </p>
            )}

            <div className="withdraw__actions">
              <button type="button" className="button button--secondary" onClick={onClose}>
                Not now
              </button>
              <button
                type="button"
                className="button button--reserve"
                onClick={() => void handleConfirm()}
                disabled={submitting}
              >
                {submitting ? "Accepting…" : "Accept place"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
