import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import { bookingApi, bookingErrorMessage, formatBookingWindow } from "./bookingApi";
import type { VenueBooking } from "./bookingTypes";
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

/** US22 AC 4: Venue Staff's queue of Requested bookings, oldest first as the API returns them. */
export function PendingBookings() {
  const [bookings, setBookings] = useState<VenueBooking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <section className="venue-bookings" aria-labelledby="pending-bookings-title">
      <h2 id="pending-bookings-title">Pending venue requests</h2>
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
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
