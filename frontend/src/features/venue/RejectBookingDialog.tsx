import { useId, useState } from "react";
import { decisionErrorMessage, formatBookingWindow } from "./bookingApi";
import type { BookingRejectWrite, VenueBooking } from "./bookingTypes";
import "../registration/registration.css";
import "../eventRequest/eventRequests.css";
import "./venues.css";

// The API refuses longer notes (BookingRejectWrite in backend/app/venue/schemas.py).
const NOTE_MAX_LENGTH = 1000;

interface RejectBookingDialogProps {
  booking: VenueBooking;
  // Rejects; throws the API's refusal (e.g. BOOKING_NOT_PENDING) for the dialog to explain.
  onConfirm: (body: BookingRejectWrite) => Promise<void>;
  onClose: () => void;
}

/**
 * US4 AC 4, 5 (SCRUM-8): Venue staff reject a request as a whole, optionally saying why and
 * suggesting another venue or arrangement. Both notes go to the coordinator; blank ones are left out.
 */
export function RejectBookingDialog({ booking, onConfirm, onClose }: RejectBookingDialogProps) {
  const titleId = useId();
  const [reason, setReason] = useState("");
  const [alternative, setAlternative] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setError(null);
    setSubmitting(true);
    const body: BookingRejectWrite = {};
    if (reason.trim()) body.reason = reason.trim();
    if (alternative.trim()) body.alternative_suggestion = alternative.trim();
    try {
      await onConfirm(body);
    } catch (refusal) {
      setError(decisionErrorMessage(refusal));
    } finally {
      setSubmitting(false);
    }
  }

  const eventName = booking.event.name || booking.event.request_reference || "Untitled event";

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="dialog__close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h3 id={titleId} className="reg-form__title">
          Reject this venue request?
        </h3>
        <p className="reg-form__meta">
          {eventName} at {booking.venue.name} · {formatBookingWindow(booking)}
        </p>
        <p className="reg-form__notice">
          The whole request is rejected and the window is freed. The coordinator is told, and the event stays open for
          them to request another venue.
        </p>

        <label className="reg-form__field">
          Reason (optional)
          <textarea className="venue-dialog__note" rows={3} maxLength={NOTE_MAX_LENGTH} value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
        <label className="reg-form__field">
          Suggested alternative (optional)
          <textarea
            className="venue-dialog__note"
            rows={2}
            maxLength={NOTE_MAX_LENGTH}
            placeholder="Another venue, time or arrangement"
            value={alternative}
            onChange={(e) => setAlternative(e.target.value)}
          />
        </label>

        {error && (
          <p className="reg-form__error" role="alert">
            {error}
          </p>
        )}

        <div className="withdraw__actions">
          {error ? (
            <button type="button" className="request-button request-button--secondary" onClick={onClose}>
              Back to requests
            </button>
          ) : (
            <>
              <button type="button" className="request-button request-button--quiet" onClick={onClose}>
                Cancel
              </button>
              <button
                type="button"
                className="request-button request-button--primary"
                onClick={() => void handleConfirm()}
                disabled={submitting}
              >
                {submitting ? "Rejecting…" : "Reject request"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
