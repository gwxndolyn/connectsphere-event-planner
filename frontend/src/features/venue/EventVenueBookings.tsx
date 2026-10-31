import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import type { EventRequest } from "../eventRequest/types";
import {
  bookingApi,
  bookingErrorMessage,
  bookingStatusLabel,
  formatBookingWindow,
  formatOccupied,
  preparationLabel,
  primaryErrorMessage,
} from "./bookingApi";
import type { EventVenueBooking, EventVenues, VenueBookingCreated } from "./bookingTypes";
import { tagLabel } from "./tags";
import { VenueArrangements } from "./VenueArrangements";
import { VenueBookingForm } from "./VenueBookingForm";
import { WithdrawBookingDialog } from "./WithdrawBookingDialog";
import "../eventRequest/eventRequests.css";
import "./venues.css";

interface EventVenueBookingsProps {
  // An approved request: the only bookable status a coordinator can open until D11 is widened.
  event: EventRequest;
}

type Notice =
  | { kind: "booked"; booking: VenueBookingCreated }
  | { kind: "withdrawn"; booking: EventVenueBooking }
  | { kind: "primary"; booking: EventVenueBooking };

function live(booking: EventVenueBooking): boolean {
  return booking.status === "requested" || booking.status === "approved";
}

/**
 * US22 (SCRUM-113): an event's venue bookings with their status, Withdraw (AC 5) and Request venue
 * (AC 2). Only the event's assigned coordinator may book it (US10a, D20): the API answers anyone else
 * with 404, which this panel explains instead of offering Request venue. US13 (SCRUM-116): each booking
 * shows its reference and the window its setup and turnaround occupy. US24 (SCRUM-129): an event can have
 * several venues, each with its purpose and allocation; one is primary (D68, Make primary); an approved
 * one can be withdrawn too (D69); and the panel says whether the venues are arranged (D67, D72).
 */
export function EventVenueBookings({ event }: EventVenueBookingsProps) {
  const [venues, setVenues] = useState<EventVenues | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  // The booking whose Withdraw is waiting for confirmation (PR #69 review).
  const [confirming, setConfirming] = useState<EventVenueBooking | null>(null);
  // The API refused this event's bookings (404): it's assigned to another coordinator (D20).
  const [notMine, setNotMine] = useState(false);
  const assigned = event.coordinator !== null;
  const bookings = venues?.bookings ?? [];

  useEffect(() => {
    // Nobody may book an unassigned event, so there's nothing to load.
    if (!assigned) return;
    let current = true;
    bookingApi
      .eventVenues(event.id)
      .then((result) => {
        if (current) setVenues(result);
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

  // After any change: the venues, the primary and the summary as the API now has them.
  async function reload() {
    try {
      setVenues(await bookingApi.eventVenues(event.id));
    } catch (reason) {
      setError(bookingErrorMessage(reason));
    }
  }

  /** Runs once the coordinator confirms in the dialog; a refusal is rethrown for it to explain. */
  async function withdraw(booking: EventVenueBooking) {
    setError(null);
    setNotice(null);
    try {
      const withdrawn = await bookingApi.withdraw(booking.id);
      const updated = { ...booking, ...withdrawn };
      setVenues((current) =>
        current && { ...current, bookings: current.bookings.map((b) => (b.id === updated.id ? updated : b)) },
      );
      setNotice({ kind: "withdrawn", booking: updated });
      setConfirming(null);
      // US24: the primary and the summary may have changed too.
      await reload();
    } catch (reason) {
      // BOOKING_NOT_LIVE: rejected or withdrawn meanwhile, so show what it is now behind the dialog.
      await reload();
      throw reason;
    }
  }

  /** US24 AC 4 (D68): the venue attendees see, once it's approved (D70). */
  async function makePrimary(booking: EventVenueBooking) {
    setError(null);
    setNotice(null);
    try {
      // The API's copy: its status says whether attendees see it yet (D70).
      setNotice({ kind: "primary", booking: { ...booking, ...(await bookingApi.makePrimary(booking.id)) } });
    } catch (reason) {
      setError(primaryErrorMessage(reason));
    }
    await reload();
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
          ) : notice.kind === "primary" ? (
            <p>
              {notice.booking.venue.name} is now the primary venue.{" "}
              {notice.booking.status === "approved"
                ? "Attendees see it now."
                : "Attendees see it once Venue staff have approved it."}
            </p>
          ) : (
            <p>
              {notice.booking.decided_at ? `${notice.booking.venue.name} withdrawn.` : `Request for ${notice.booking.venue.name} withdrawn.`}
            </p>
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
        <>
          {venues && <VenueArrangements venues={venues} audience="coordinator" />}
          <ul className="venue-booking-list" aria-label="This event's venue bookings">
            {bookings.map((booking) => {
              const window = formatBookingWindow(booking);
              return (
                <li key={booking.id} className="venue-booking-row" aria-label={`${booking.venue.name}, ${window}`}>
                  <div className="venue-booking-row__main">
                    <strong>
                      {booking.venue.name} · {booking.purpose}
                    </strong>
                    <span>{window}</span>
                    <span className="venue-booking-row__occupied">
                      {booking.reference} · Occupied {formatOccupied(booking)} with setup and turnaround
                    </span>
                    <span>
                      {booking.expected_attendees} attending · {tagLabel(booking.room_layout)}
                    </span>
                    {/* US24 AC 7 (D73): Venue staff record it; the coordinator reads it. */}
                    {booking.status === "approved" && <span>Preparation: {preparationLabel(booking.preparation_status)}</span>}
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
                    {booking.unavailability?.kind === "venue_inactive" && (
                      <span className="venue-booking-row__decision">This venue is no longer available.</span>
                    )}
                  </div>
                  {booking.is_primary && <span className="venue-badge venue-badge--primary">Primary</span>}
                  <span className={`venue-booking-status venue-booking-status--${booking.status}`}>
                    {bookingStatusLabel(booking.status)}
                  </span>
                  {live(booking) && !booking.is_primary && (
                    <button
                      type="button"
                      className="request-button request-button--secondary"
                      onClick={() => void makePrimary(booking)}
                    >
                      Make primary
                    </button>
                  )}
                  {/* US24 (D69): an approved venue can be withdrawn too; Venue staff are told. */}
                  {live(booking) && (
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
        </>
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
