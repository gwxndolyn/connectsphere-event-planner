import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { bookingApi, bookingErrorMessage, decisionErrorMessage, formatBookingWindow } from "./bookingApi";
import type { BookingRejectWrite, VenueBooking } from "./bookingTypes";
import { RejectBookingDialog } from "./RejectBookingDialog";
import { tagLabel } from "./tags";
import "../eventRequest/eventRequests.css";
import "./venues.css";

function eventName(booking: VenueBooking): string {
  return booking.event.name || booking.event.request_reference || "Untitled event";
}

function pendingErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === "FORBIDDEN") return "Only Venue staff can see pending venue requests.";
  return bookingErrorMessage(error);
}

type Notice = { kind: "approved" | "rejected"; booking: VenueBooking };

/**
 * US22 AC 4: Venue Staff's queue of Requested bookings, oldest first as the API returns them.
 * US4 (SCRUM-8): each shows the event's timing and needs (AC 1) and is approved or rejected as a whole
 * (AC 7). A refused approval (the venue is booked, held or blocked, AC 3) is explained on the row and
 * the request stays here, to be rejected; there's no override.
 */
export function PendingBookings() {
  const [bookings, setBookings] = useState<VenueBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  // Why approving a row was refused, by booking id.
  const [refusals, setRefusals] = useState<Record<string, string>>({});
  const [approving, setApproving] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<VenueBooking | null>(null);

  useEffect(() => {
    let current = true;
    bookingApi
      .pending()
      .then((result) => {
        if (current) setBookings(result);
      })
      .catch((reason: unknown) => {
        if (current) setError(pendingErrorMessage(reason));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, []);

  // After a decision or a refusal: show the queue as the API now has it, keeping the row refusals.
  async function reload() {
    try {
      setBookings(await bookingApi.pending());
    } catch (reason) {
      setError(pendingErrorMessage(reason));
    }
  }

  function decided(booking: VenueBooking, kind: Notice["kind"]) {
    setBookings((current) => current.filter((b) => b.id !== booking.id));
    setNotice({ kind, booking });
  }

  async function approve(booking: VenueBooking) {
    setNotice(null);
    setRefusals((current) => {
      const rest = { ...current };
      delete rest[booking.id];
      return rest;
    });
    setApproving(booking.id);
    try {
      decided(await bookingApi.approve(booking.id), "approved");
    } catch (reason) {
      setRefusals((current) => ({ ...current, [booking.id]: decisionErrorMessage(reason) }));
      // BOOKING_NOT_PENDING: decided or withdrawn meanwhile, so the row may be gone now.
      if (reason instanceof ApiError && reason.code === "BOOKING_NOT_PENDING") await reload();
    } finally {
      setApproving(null);
    }
  }

  /** Runs once Venue staff confirm in the dialog; a refusal is rethrown for it to explain. */
  async function reject(booking: VenueBooking, body: BookingRejectWrite) {
    setNotice(null);
    try {
      decided(await bookingApi.reject(booking.id, body), "rejected");
      setRejecting(null);
    } catch (reason) {
      await reload();
      throw reason;
    }
  }

  return (
    <section className="venue-bookings" aria-labelledby="pending-bookings-title">
      <h2 id="pending-bookings-title">Pending venue requests</h2>
      {notice && (
        <div className="request-notice" role="status">
          {notice.kind === "approved"
            ? `Approved: ${notice.booking.venue.name} is reserved for ${eventName(notice.booking)}, ${formatBookingWindow(notice.booking)}.`
            : `Rejected the request for ${notice.booking.venue.name} for ${eventName(notice.booking)}.`}{" "}
          The coordinator has been notified.
        </div>
      )}
      {error ? (
        <div className="request-alert" role="alert">
          {error}
        </div>
      ) : loading ? (
        <p className="request-empty">Loading pending requests…</p>
      ) : bookings.length === 0 ? (
        <p className="request-empty">No venue requests are waiting for review.</p>
      ) : (
        <ul className="venue-booking-list" aria-label="Pending venue requests">
          {bookings.map((booking) => {
            const needs = [...booking.required_facilities, ...booking.required_accessibility_features].map(tagLabel);
            return (
              <li key={booking.id} className="venue-booking-row" aria-label={`${eventName(booking)} at ${booking.venue.name}`}>
                <div className="venue-booking-row__main">
                  <strong>
                    {eventName(booking)} at {booking.venue.name}
                  </strong>
                  <span>{formatBookingWindow(booking)}</span>
                  <span>
                    {booking.expected_attendees} attending · {tagLabel(booking.room_layout)}
                  </span>
                  {needs.length > 0 && <span>Needs: {needs.join(", ")}</span>}
                  {booking.special_requirements && <span>“{booking.special_requirements}”</span>}
                  {refusals[booking.id] && (
                    <span className="venue-booking-row__error" role="alert">
                      {refusals[booking.id]}
                    </span>
                  )}
                </div>
                <div className="venue-booking-row__actions">
                  <button
                    type="button"
                    className="request-button request-button--primary"
                    disabled={approving === booking.id}
                    onClick={() => void approve(booking)}
                  >
                    {approving === booking.id ? "Approving…" : "Approve"}
                  </button>
                  <button
                    type="button"
                    className="request-button request-button--secondary"
                    onClick={() => {
                      setNotice(null);
                      setRejecting(booking);
                    }}
                  >
                    Reject
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {rejecting && (
        <RejectBookingDialog
          booking={rejecting}
          onConfirm={(body) => reject(rejecting, body)}
          onClose={() => setRejecting(null)}
        />
      )}
    </section>
  );
}
