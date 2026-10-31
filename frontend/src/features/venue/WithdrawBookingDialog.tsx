import { useId, useState } from "react";
import { bookingErrorMessage, formatBookingWindow } from "./bookingApi";
import type { VenueBooking } from "./bookingTypes";
import "../registration/registration.css";
import "../eventRequest/eventRequests.css";

interface WithdrawBookingDialogProps {
  booking: VenueBooking;
  // Withdraws; throws the API's refusal (e.g. BOOKING_NOT_LIVE) for the dialog to explain.
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

/**
 * US22 AC 5 (PR #69 review): withdrawing frees the window for anyone at once, so it asks first,
 * like the registration WithdrawDialog. The panel shows the result once the API has accepted it.
 */
export function WithdrawBookingDialog({ booking, onConfirm, onClose }: WithdrawBookingDialogProps) {
  const titleId = useId();
  // US24 (D69): an approved venue can be withdrawn too, to change or cancel one of the event's venues.
  const approved = booking.status === "approved";
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setError(null);
    setSubmitting(true);
    try {
      await onConfirm();
    } catch (reason) {
      setError(bookingErrorMessage(reason));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="dialog__close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h3 id={titleId} className="reg-form__title">
          {approved ? "Withdraw this approved venue?" : "Withdraw this venue request?"}
        </h3>
        <p className="reg-form__meta">
          {booking.venue.name} · {formatBookingWindow(booking)}
        </p>
        {approved ? (
          <p className="reg-form__notice">
            {booking.venue.name} is released straight away and Venue staff will be told. The event's other venues stay as they
            are. To use it again you'd have to request it again, if it's still free.
          </p>
        ) : (
          <p className="reg-form__notice">
            The window is released straight away: any coordinator can request {booking.venue.name} for that time, and Venue
            staff stop seeing this request. To get it back you'd have to request it again, if it's still free.
          </p>
        )}

        {error && (
          <p className="reg-form__error" role="alert">
            {error}
          </p>
        )}

        <div className="withdraw__actions">
          {error ? (
            <button type="button" className="request-button request-button--secondary" onClick={onClose}>
              Back to bookings
            </button>
          ) : (
            <>
              <button type="button" className="request-button request-button--quiet" onClick={onClose}>
                {approved ? "Keep venue" : "Keep request"}
              </button>
              <button
                type="button"
                className="request-button request-button--primary"
                onClick={() => void handleConfirm()}
                disabled={submitting}
              >
                {submitting ? "Withdrawing…" : approved ? "Withdraw venue" : "Withdraw request"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
