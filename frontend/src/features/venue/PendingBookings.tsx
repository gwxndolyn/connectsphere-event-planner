import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import {
  bookingApi,
  bookingErrorMessage,
  decisionErrorMessage,
  eventName,
  formatBookingWindow,
  formatOccupied,
  formatVenueTime,
  formatWindowTimes,
} from "./bookingApi";
import type { BookingConflict, BookingEvaluation, BookingRejectWrite, VenueBooking } from "./bookingTypes";
import { RejectBookingDialog } from "./RejectBookingDialog";
import { tagLabel } from "./tags";
import "../eventRequest/eventRequests.css";
import "./venues.css";

function pendingErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === "FORBIDDEN") return "Only Venue staff can see pending venue requests.";
  return bookingErrorMessage(error);
}

type Notice = { kind: "approved" | "rejected"; booking: VenueBooking };

// A row's evaluation: loading (absent), what the API found, or that it couldn't be checked.
type EvaluationState = BookingEvaluation | "failed";

function conflictText(conflict: BookingConflict): string {
  const overlap = `overlap ${formatWindowTimes(conflict.overlap)}`;
  if (conflict.kind === "block") {
    return `Venue closure${conflict.note ? ` (${conflict.note})` : ""}, ${formatBookingWindow(conflict)}: ${overlap}`;
  }
  return `Booking ${conflict.reference ?? ""}, ${formatBookingWindow(conflict)}: ${overlap}`;
}

/** US13 AC 3 to 5 (D36): what stands in the way of approving this request now. */
function EvaluationSummary({ evaluation }: { evaluation: EvaluationState | undefined }) {
  if (evaluation === undefined) return <span className="venue-booking-row__check">Checking for conflicts…</span>;
  if (evaluation === "failed") {
    return <span className="venue-booking-row__check">Couldn't check for conflicts; approving still checks.</span>;
  }
  if (evaluation.clear) return <span className="venue-booking-row__check">No conflicts with setup and turnaround.</span>;
  const hours = evaluation.outside_hours;
  return (
    <ul className="venue-booking-row__conflicts" aria-label="Conflicts">
      {hours && (
        <li>
          Outside opening hours ({formatVenueTime(hours.opens_at)} – {formatVenueTime(hours.closes_at)}) with setup and
          turnaround
        </li>
      )}
      {/* The index too: two blocks can start, or even end, at the same time. */}
      {evaluation.conflicts.map((conflict, index) => (
        <li key={`${conflict.kind}-${conflict.reference ?? conflict.starts_at}-${index}`}>{conflictText(conflict)}</li>
      ))}
    </ul>
  );
}

/**
 * US22 AC 4: Venue Staff's queue of Requested bookings, oldest first as the API returns them.
 * US4 (SCRUM-8): each shows the event's timing and needs (AC 1) and is approved or rejected as a whole
 * (AC 7). A refused approval (the venue is booked, held or blocked, AC 3) is explained on the row and
 * the request stays here, to be rejected; there's no override. US13 (SCRUM-116, AC 4): each row shows
 * its reference and occupied window, and the evaluation lists anything that now overlaps it (with the
 * overlap and the clashing reference) or an opening-hours breach, before Venue staff decide.
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
  const [evaluations, setEvaluations] = useState<Record<string, EvaluationState>>({});

  /** Each row's evaluation, fetched alongside; a row that fails says so and can still be decided. */
  function evaluate(list: VenueBooking[], isCurrent: () => boolean = () => true) {
    for (const booking of list) {
      bookingApi
        .evaluation(booking.id)
        .then((result): EvaluationState => result)
        .catch((): EvaluationState => "failed")
        .then((result) => {
          if (isCurrent()) setEvaluations((now) => ({ ...now, [booking.id]: result }));
        });
    }
  }

  useEffect(() => {
    let current = true;
    bookingApi
      .pending()
      .then((result) => {
        if (!current) return;
        setBookings(result);
        evaluate(result, () => current);
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
      const result = await bookingApi.pending();
      setBookings(result);
      evaluate(result);
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
      // Otherwise show what stands in the way now, which may have changed since the list loaded.
      else evaluate([booking]);
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
      // US16b D51: the request isn't this user's to decide. It stays, with the reason on its row.
      if (reason instanceof ApiError && reason.code === "SELF_DECISION_NOT_ALLOWED") {
        setRejecting(null);
        setRefusals((current) => ({ ...current, [booking.id]: decisionErrorMessage(reason) }));
        return;
      }
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
            ? `Approved: ${notice.booking.venue.name} is reserved for ${eventName(notice.booking.event)}, ${formatBookingWindow(notice.booking)}.`
            : `Rejected the request for ${notice.booking.venue.name} for ${eventName(notice.booking.event)}.`}{" "}
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
              <li key={booking.id} className="venue-booking-row" aria-label={`${eventName(booking.event)} at ${booking.venue.name}`}>
                <div className="venue-booking-row__main">
                  <strong>
                    {eventName(booking.event)} at {booking.venue.name}
                  </strong>
                  <span>{formatBookingWindow(booking)}</span>
                  <span className="venue-booking-row__occupied">
                    {booking.reference} · Occupied {formatOccupied(booking)} with setup and turnaround
                  </span>
                  <span>
                    {booking.expected_attendees} attending · {tagLabel(booking.room_layout)}
                  </span>
                  {needs.length > 0 && <span>Needs: {needs.join(", ")}</span>}
                  {booking.special_requirements && <span>“{booking.special_requirements}”</span>}
                  <EvaluationSummary evaluation={evaluations[booking.id]} />
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
