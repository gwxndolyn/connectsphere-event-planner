import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import type { EventRequest } from "../eventRequest/types";
import { bookingApi, bookingErrorMessage, bookingStatusLabel, formatBookingWindow, formatOccupied } from "./bookingApi";
import type { VenueBooking, VenueBookingCreated } from "./bookingTypes";
import { tagLabel } from "./tags";
import { VenueBookingForm } from "./VenueBookingForm";
import { WithdrawBookingDialog } from "./WithdrawBookingDialog";
import "../eventRequest/eventRequests.css";
import "./venues.css";

interface EventVenueBookingsProps {
  // An approved request: the only bookable status a coordinator can open until D11 is widened.
  event: EventRequest;
}

type Notice = { kind: "booked"; booking: VenueBookingCreated } | { kind: "withdrawn"; booking: VenueBooking };

/**
 * US22 (SCRUM-113): an event's venue bookings with their status, Withdraw on a pending one (AC 5),
 * and Request venue (AC 2). Only the event's assigned coordinator may book it (US10a, D20): the API
 * answers anyone else with 404, which this panel explains instead of offering Request venue. US13
 * (SCRUM-116): each booking shows its reference and the window its setup and turnaround occupy.
 */
export function EventVenueBookings({ event }: EventVenueBookingsProps) {
  const [bookings, setBookings] = useState<VenueBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  // The booking whose Withdraw is waiting for confirmation (PR #69 review).
  const [confirming, setConfirming] = useState<VenueBooking | null>(null);
  // The API refused this event's bookings (404): it's assigned to another coordinator (D20).
  const [notMine, setNotMine] = useState(false);
  const assigned = event.coordinator !== null;

  useEffect(() => {
    // Nobody may book an unassigned event, so there's nothing to load.
    if (!assigned) return;
    let current = true;
    bookingApi
      .forEvent(event.id)
      .then((result) => {
        if (current) setBookings(result);
      })
      .catch((reason: unknown) => {
        if (!current) return;
        if (reason instanceof ApiError && reason.code === "NOT_FOUND") setNotMine(true);
        else setError(bookingErrorMessage(reason));
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => {
      current = false;
    };
  }, [event.id, assigned]);

  const blocked = !assigned
    ? "No coordinator is assigned to this event yet, so no venue can be requested for it. A Coordinator Lead assigns one."
    : notMine
      ? `Only ${event.coordinator?.name}, the coordinator assigned to this event, can request a venue for it.`
      : null;

  // After a booking or a refused withdrawal: show the list as the API now has it.
  async function reload() {
    try {
      setBookings(await bookingApi.forEvent(event.id));
    } catch (reason) {
      setError(bookingErrorMessage(reason));
    }
  }

  /** Runs once the coordinator confirms in the dialog; a refusal is rethrown for it to explain. */
  async function withdraw(booking: VenueBooking) {
    setError(null);
    setNotice(null);
    try {
      const withdrawn = await bookingApi.withdraw(booking.id);
      setBookings((current) => current.map((b) => (b.id === withdrawn.id ? withdrawn : b)));
      setNotice({ kind: "withdrawn", booking: withdrawn });
      setConfirming(null);
    } catch (reason) {
      // BOOKING_NOT_LIVE: rejected or withdrawn meanwhile, so show what it is now behind the dialog.
      await reload();
      throw reason;
    }
  }

  return (
    <section className="venue-bookings" aria-labelledby="venue-bookings-title">
      <div className="venue-bookings__head">
        <h2 id="venue-bookings-title">Venue bookings</h2>
        {!requesting && !blocked && (
          <button
            type="button"
            className="request-button request-button--primary"
            onClick={() => {
              setNotice(null);
              setError(null);
              setRequesting(true);
            }}
          >
            Request venue
          </button>
        )}
      </div>

      {notice && (
        <div className="request-notice" role="status">
          {notice.kind === "booked" ? (
            <>
              <p>
                Venue requested: {notice.booking.venue.name}, {formatBookingWindow(notice.booking)} (
                {notice.booking.reference}). Venue staff have been notified.
              </p>
              {notice.booking.warnings.length > 0 && (
                <ul className="venue-booking__warnings" aria-label="Warnings from the booking">
                  {notice.booking.warnings.map((warning) => (
                    <li key={`${warning.field}-${warning.item}`}>{warning.message}</li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p>Request for {notice.booking.venue.name} withdrawn.</p>
          )}
        </div>
      )}
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}

      {blocked ? (
        <p className="request-empty">{blocked}</p>
      ) : requesting ? (
        <VenueBookingForm
          event={event}
          onCancel={() => setRequesting(false)}
          onBooked={(booking) => {
            setRequesting(false);
            setNotice({ kind: "booked", booking });
            void reload();
          }}
        />
      ) : loading ? (
        <p className="request-empty">Loading venue bookings…</p>
      ) : bookings.length === 0 ? (
        <p className="request-empty">No venue requested for this event yet.</p>
      ) : (
        <ul className="venue-booking-list" aria-label="This event's venue bookings">
          {bookings.map((booking) => {
            const window = formatBookingWindow(booking);
            return (
              <li key={booking.id} className="venue-booking-row" aria-label={`${booking.venue.name}, ${window}`}>
                <div className="venue-booking-row__main">
                  <strong>{booking.venue.name}</strong>
                  <span>{window}</span>
                  <span className="venue-booking-row__occupied">
                    {booking.reference} · Occupied {formatOccupied(booking)} with setup and turnaround
                  </span>
                  <span>
                    {booking.expected_attendees} attending · {tagLabel(booking.room_layout)}
                  </span>
                  {/* US4 AC 5, 8: why Venue staff said no, and what they'd suggest; the event can book again. */}
                  {booking.status === "rejected" && (
                    <>
                      {booking.rejection_reason && (
                        <span className="venue-booking-row__decision">Reason: {booking.rejection_reason}</span>
                      )}
                      {booking.alternative_suggestion && (
                        <span className="venue-booking-row__decision">Suggested instead: {booking.alternative_suggestion}</span>
                      )}
                    </>
                  )}
                </div>
                <span className={`venue-booking-status venue-booking-status--${booking.status}`}>
                  {bookingStatusLabel(booking.status)}
                </span>
                {booking.status === "requested" && (
                  <button
                    type="button"
                    className="request-button request-button--quiet"
                    onClick={() => {
                      setNotice(null);
                      setConfirming(booking);
                    }}
                  >
                    Withdraw
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {confirming && (
        <WithdrawBookingDialog
          booking={confirming}
          onConfirm={() => withdraw(confirming)}
          onClose={() => setConfirming(null)}
        />
      )}
    </section>
  );
}
