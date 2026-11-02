import { useEffect, useState } from "react";
import { formatInstantDateTime } from "../registration/datetime";
import { bookingApi, bookingErrorMessage } from "./bookingApi";
import type { HoldEvent, VenueBookingCreated } from "./bookingTypes";
import { VenueBookingForm } from "./VenueBookingForm";
import "../eventRequest/eventRequests.css";
import "./venues.css";

function eventLabel(event: HoldEvent): string {
  const name = event.name || event.request_reference || "Unnamed event";
  return event.request_reference && event.name ? `${name} (${event.request_reference})` : name;
}

/**
 * US25 (SCRUM-93) AC 1: Venue staff hold a venue for an Approved or Planning event and a time, until an expiry, so
 * its coordinator can finalise arrangements. The form is the request form with an expiry; the API checks the rest
 * (the event's schedule, capacity, hours, other bookings and holds) and tells the coordinator.
 */
export function HoldVenue() {
  const [events, setEvents] = useState<HoldEvent[] | null>(null);
  const [eventId, setEventId] = useState("");
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [placed, setPlaced] = useState<VenueBookingCreated | null>(null);

  useEffect(() => {
    if (!open || events !== null) return;
    let current = true;
    bookingApi
      .holdEvents()
      .then((result) => {
        if (current) setEvents(result);
      })
      .catch((reason: unknown) => {
        if (current) {
          setEvents([]);
          setError(bookingErrorMessage(reason));
        }
      });
    return () => {
      current = false;
    };
  }, [open, events]);

  const event = events?.find((candidate) => candidate.id === eventId);

  return (
    <section className="venue-holds" aria-labelledby="venue-holds-title">
      <div className="venue-holds__heading">
        <h2 id="venue-holds-title">Hold a venue</h2>
        {!open && (
          <button
            type="button"
            className="request-button request-button--secondary"
            onClick={() => {
              setOpen(true);
              setPlaced(null);
              // After a failed load, opening again tries again (PR review).
              if (error) {
                setError(null);
                setEvents(null);
              }
            }}
          >
            Place a hold
          </button>
        )}
      </div>
      {placed && (
        <p className="request-notice" role="status">
          Held {placed.venue.name} for {placed.event.name || placed.event.request_reference || "the event"} until{" "}
          {placed.hold_expires_at ? formatInstantDateTime(placed.hold_expires_at) : "its expiry"}. The coordinator has
          been told.
        </p>
      )}
      {error && (
        <div className="request-alert" role="alert">
          {error}
        </div>
      )}
      {open && (
        <>
          <div className="request-field">
            <label htmlFor="venue-hold-event">Event</label>
            <select id="venue-hold-event" value={eventId} onChange={(changed) => setEventId(changed.target.value)}>
              <option value="">{events === null ? "Loading events…" : "Choose an event"}</option>
              {(events ?? []).map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {eventLabel(candidate)}
                </option>
              ))}
            </select>
          </div>
          {event && (
            <VenueBookingForm
              key={event.id}
              event={event}
              hold
              onBooked={(booking) => {
                setPlaced(booking);
                setOpen(false);
                setEventId("");
              }}
              onCancel={() => {
                setOpen(false);
                setEventId("");
              }}
            />
          )}
        </>
      )}
    </section>
  );
}
