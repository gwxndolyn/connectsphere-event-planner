import { useEffect, useId, useState } from "react";
import type { EventRequest } from "../eventRequest/types";
import { bookingApi, bookingStatusLabel, formatBookingWindow, nextActionLabel, preparationLabel } from "./bookingApi";
import type { BookingUnavailability, EventVenues } from "./bookingTypes";
import { VenueArrangements } from "./VenueArrangements";
import "../eventRequest/eventRequests.css";
import "./venues.css";

/** Why a venue needs replacing, as the Organiser reads it (D71). */
function unavailabilityText(unavailability: BookingUnavailability): string {
  if (unavailability.kind === "venue_inactive") return "This venue is no longer available.";
  const reason = unavailability.reason ? `: ${unavailability.reason}` : "";
  // A reason Venue staff already ended with ., ! or ? gets no second full stop.
  const stop = /[.!?]$/.test(reason) ? "" : ".";
  const instead = unavailability.alternative_suggestion ? ` Suggested instead: ${unavailability.alternative_suggestion}` : "";
  return `Venue staff rejected it${reason}${stop}${instead}`;
}

interface EventVenuesOverviewProps {
  // An event the Organiser created, approved or later (D71).
  event: EventRequest;
}

/**
 * US24 AC 4 (SCRUM-129, D71): the Organiser's read-only view of their event's venues: each one's
 * status, whether it's the primary venue attendees see, its preparation, anything that stands in its
 * way and who acts next, and whether the venues are arranged. The coordinator makes every change.
 */
export function EventVenuesOverview({ event }: EventVenuesOverviewProps) {
  const titleId = useId();
  const [venues, setVenues] = useState<EventVenues | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    bookingApi
      .eventVenues(event.id)
      .then((result) => {
        if (current) setVenues(result);
      })
      .catch(() => {
        if (current) setError("This event's venues can't be shown right now.");
      });
    return () => {
      current = false;
    };
  }, [event.id]);

  return (
    <section className="venue-bookings venue-overview" aria-labelledby={titleId}>
      <h2 id={titleId}>Venues</h2>
      {error ? (
        <div className="request-alert" role="alert">
          {error}
        </div>
      ) : !venues ? (
        <p className="request-empty">Loading venues…</p>
      ) : venues.bookings.length === 0 ? (
        <p className="request-empty">No venue has been requested for this event yet.</p>
      ) : (
        <>
          <VenueArrangements venues={venues} audience="organiser" />
          <ul className="venue-booking-list" aria-label="This event's venues">
            {venues.bookings.map((booking) => {
              const window = formatBookingWindow(booking);
              return (
                <li
                  key={booking.id}
                  className="venue-booking-row"
                  aria-label={`${booking.purpose}: ${booking.venue.name}, ${window}`}
                >
                  <div className="venue-booking-row__main">
                    <strong>
                      {booking.purpose} · {booking.venue.name}
                    </strong>
                    <span>{window}</span>
                    {booking.status === "approved" && <span>Preparation: {preparationLabel(booking.preparation_status)}</span>}
                    {booking.unavailability && (
                      <span className="venue-booking-row__decision">{unavailabilityText(booking.unavailability)}</span>
                    )}
                    <span>Next: {nextActionLabel(booking.next_action)}</span>
                  </div>
                  {booking.is_primary && <span className="venue-badge venue-badge--primary">Primary</span>}
                  <span className={`venue-booking-status venue-booking-status--${booking.status}`}>
                    {bookingStatusLabel(booking.status)}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
