import { useEffect, useState } from "react";
import { bookingApi, bookingErrorMessage, eventName, formatBookingWindow, formatOccupied } from "./bookingApi";
import type { VenueBooking } from "./bookingTypes";
import "../eventRequest/eventRequests.css";
import "./venues.css";

// The API refuses longer reasons (RestoreDeclineWrite in backend/app/venue/schemas.py).
const REASON_MAX_LENGTH = 1000;

type Notice = { kind: "confirmed" | "declined"; booking: VenueBooking };

/**
 * US23b (SCRUM-91) AC 5 (D118): a coordinator asked to restore a booking that needed rearrangement, once its venue
 * was free again. Venue staff confirm, which checks the whole occupied window again and gives the event its venue
 * back, or decline, optionally saying why. Hidden when none waits.
 */
export function RestoreRequests() {
  const [requests, setRequests] = useState<VenueBooking[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  // The request whose Decline is open, with its optional reason.
  const [declining, setDeclining] = useState<{ id: string; reason: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    bookingApi
      .restoreRequests()
      .then((result) => {
        if (current) setRequests(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(bookingErrorMessage(reason));
      });
    return () => {
      current = false;
    };
  }, []);

  async function decide(booking: VenueBooking, kind: Notice["kind"], reason?: string) {
    setBusy(booking.id);
    setError(null);
    setNotice(null);
    try {
      const result =
        kind === "confirmed"
          ? await bookingApi.confirmRestore(booking.id)
          : await bookingApi.declineRestore(booking.id, reason?.trim() || undefined);
      setNotice({ kind, booking: { ...booking, ...result } });
      setDeclining(null);
    } catch (reason) {
      setError(bookingErrorMessage(reason));
    } finally {
      setBusy(null);
    }
    try {
      setRequests(await bookingApi.restoreRequests());
    } catch (reason) {
      setError(bookingErrorMessage(reason));
    }
  }

  if (requests.length === 0 && !error && !notice) return null;

  return (
    <section className="venue-bookings" aria-labelledby="restore-requests-title">
      <h2 id="restore-requests-title">Requests to restore a booking ({requests.length})</h2>
      {notice && (
        <div className="request-notice" role="status">
          {notice.kind === "confirmed"
            ? `${notice.booking.reference} restored: ${notice.booking.venue.name} is back with ${eventName(notice.booking.event)}. The coordinator has been told.`
            : `Restore of ${notice.booking.reference} declined. It still needs rearrangement; the coordinator has been told.`}
        </div>
      )}
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {requests.length > 0 && (
        <ul className="venue-booking-list" aria-label="Requests to restore a booking">
          {requests.map((booking) => (
            <li
              key={booking.id}
              className="venue-booking-row"
              aria-label={`${eventName(booking.event)} at ${booking.venue.name}`}
            >
              <div className="venue-booking-row__main">
                <strong>
                  {eventName(booking.event)} · {booking.venue.name}
                </strong>
                <span>{formatBookingWindow(booking)}</span>
                <span className="venue-booking-row__occupied">
                  {booking.reference} · Occupied {formatOccupied(booking)} with setup and turnaround
                </span>
                <span>Confirming checks again that nothing makes the venue unavailable over that time.</span>
              </div>
              {declining?.id === booking.id ? (
                <div className="venue-booking-row__confirm" role="group" aria-label="Decline the restore">
                  <label htmlFor={`restore-decline-${booking.id}`}>Reason (optional)</label>
                  <input
                    id={`restore-decline-${booking.id}`}
                    type="text"
                    maxLength={REASON_MAX_LENGTH}
                    value={declining.reason}
                    onChange={(changed) => setDeclining({ id: booking.id, reason: changed.target.value })}
                  />
                  <button type="button" className="request-button request-button--quiet" onClick={() => setDeclining(null)}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="request-button request-button--secondary"
                    disabled={busy === booking.id}
                    onClick={() => void decide(booking, "declined", declining.reason)}
                  >
                    Decline restore
                  </button>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    className="request-button request-button--primary"
                    disabled={busy === booking.id}
                    onClick={() => void decide(booking, "confirmed")}
                  >
                    Confirm restore
                  </button>
                  <button
                    type="button"
                    className="request-button request-button--quiet"
                    onClick={() => setDeclining({ id: booking.id, reason: "" })}
                  >
                    Decline
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
