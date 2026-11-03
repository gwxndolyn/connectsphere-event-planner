import { useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import type { EventRequest } from "../eventRequest/types";
import { formatInstantDateTime } from "../registration/datetime";
import {
  bookingApi,
  bookingErrorMessage,
  bookingStatusLabel,
  formatBookingWindow,
  formatOccupied,
  holdCountdown,
  preparationLabel,
  primaryErrorMessage,
} from "./bookingApi";
import type { EventVenueBooking, EventVenues, VenueBookingCreated } from "./bookingTypes";
import { tagLabel } from "./tags";
import { blockReasonLabel, formatBlockPeriod } from "./blockApi";
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
  | { kind: "primary"; booking: EventVenueBooking }
  // US25 (SCRUM-93): a hold confirmed into a request (AC 5), or declined (AC 7).
  | { kind: "confirmed"; booking: EventVenueBooking }
  | { kind: "declined"; booking: EventVenueBooking }
  // US23b (SCRUM-91): a replacement requested (AC 3), or a restore asked for (AC 5).
  | { kind: "replacing"; booking: VenueBookingCreated; replaces: EventVenueBooking }
  | { kind: "restore"; booking: EventVenueBooking };


function live(booking: EventVenueBooking): boolean {
  return booking.status === "requested" || booking.status === "approved";
}

/** US23a (SCRUM-90) AC 3: the venue became unavailable for part of this booking's or hold's window. */
function needsRearrangement(booking: EventVenueBooking): boolean {
  return booking.unavailability?.kind === "venue_unavailable";
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
  // US25: the hold whose Decline is waiting for confirmation, as Withdraw does (PR review).
  const [declining, setDeclining] = useState<string | null>(null);
  // The API refused this event's bookings (404): it's assigned to another coordinator (D20).
  const [notMine, setNotMine] = useState(false);
  // US23b (SCRUM-91) AC 2: the booking needing rearrangement whose replacement is being found.
  const [replacing, setReplacing] = useState<EventVenueBooking | null>(null);
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

  /** US25 AC 5, 7: confirm a held venue into a request for Venue staff, or decline it (withdraw, D110). */
  async function decideHold(booking: EventVenueBooking, action: "confirmed" | "declined") {
    setError(null);
    setNotice(null);
    setDeclining(null);
    try {
      const result = action === "confirmed" ? await bookingApi.confirmHold(booking.id) : await bookingApi.withdraw(booking.id);
      setNotice({ kind: action, booking: { ...booking, ...result } });
    } catch (reason) {
      setError(bookingErrorMessage(reason));
    }
    await reload();
  }

  /** US23b AC 5 (D118): ask Venue staff to restore a booking once its venue is free again. */
  async function requestRestore(booking: EventVenueBooking) {
    setError(null);
    setNotice(null);
    try {
      setNotice({ kind: "restore", booking: { ...booking, ...(await bookingApi.requestRestore(booking.id)) } });
    } catch (reason) {
      setError(bookingErrorMessage(reason));
    }
    await reload();
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
        {!requesting && !replacing && !blocked && (
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
          ) : notice.kind === "confirmed" ? (
            <p>
              Hold confirmed: {notice.booking.venue.name} is now a request. Venue staff have been notified and must
              approve it
              {notice.booking.hold_expires_at ? ` by ${formatInstantDateTime(notice.booking.hold_expires_at)}` : ""}.
            </p>
          ) : notice.kind === "replacing" ? (
            <p>
              Replacement requested: {notice.booking.venue.name}, {formatBookingWindow(notice.booking)} (
              {notice.booking.reference}). Venue staff have been notified; {notice.replaces.reference} at{" "}
              {notice.replaces.venue.name} is replaced once they approve it.
            </p>
          ) : notice.kind === "restore" ? (
            <p>
              Restore requested: Venue staff have been asked to give {notice.booking.venue.name} back to this event (
              {notice.booking.reference}).
            </p>
          ) : notice.kind === "declined" ? (
            <p>Hold on {notice.booking.venue.name} declined. The venue is free again.</p>
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
      ) : replacing ? (
        <VenueBookingForm
          event={event}
          replacing={replacing}
          onCancel={() => setReplacing(null)}
          onBooked={(booking) => {
            setNotice({ kind: "replacing", booking, replaces: replacing });
            setReplacing(null);
            void reload();
          }}
        />
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
              // US23b (SCRUM-91): the replacement waiting for or approved by Venue staff, and the booking replaced.
              const replacement = bookings.find((b) => b.id === booking.replacement_booking_id);
              const replacedBy = bookings.find((b) => b.replaces_booking_id === booking.id && b.status === "approved");
              const replaces = bookings.find((b) => b.id === booking.replaces_booking_id);
              const block = booking.unavailability?.kind === "venue_unavailable" ? booking.unavailability.block : null;
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
                    {/* US25 (SCRUM-93): until when the venue is held (AC 4), and the deadline once confirmed (AC 5). */}
                    {booking.status === "held" && booking.hold_expires_at && (
                      <span className="venue-booking-row__hold">
                        Held for this event until {formatInstantDateTime(booking.hold_expires_at)} (
                        {holdCountdown(booking.hold_expires_at)}). Confirm it to request it, or decline it.
                      </span>
                    )}
                    {booking.status === "requested" && booking.hold_expires_at && (
                      <span className="venue-booking-row__hold">
                        From a hold: Venue staff must approve it by {formatInstantDateTime(booking.hold_expires_at)}.
                      </span>
                    )}
                    {booking.status === "expired" && booking.expired_at && (
                      <span className="venue-booking-row__decision">
                        The hold expired on {formatInstantDateTime(booking.expired_at)}. The venue is free again.
                      </span>
                    )}
                    {booking.unavailability?.kind === "venue_inactive" && (
                      <span className="venue-booking-row__decision">This venue is no longer available.</span>
                    )}
                    {/* US23a (SCRUM-90) AC 3, 4: the venue became unavailable; the coordinator rearranges it. */}
                    {block && !block.ended_early_at && (
                      <span className="venue-booking-row__decision">
                        Needs rearrangement: the venue is unavailable from {formatBlockPeriod(block)}
                        {block.note ? `: ${block.note}` : ""}. Find a replacement venue, or withdraw it.
                      </span>
                    )}
                    {/* US23b (SCRUM-91) AC 5 (D118): Venue staff ended the period early, so it may be restored. */}
                    {block?.ended_early_at && (
                      <span className="venue-booking-row__decision">
                        Needs rearrangement: the venue was unavailable ({blockReasonLabel(block.reason)}
                        {block.note ? `: ${block.note}` : ""}), but Venue staff ended that early on{" "}
                        {formatInstantDateTime(block.ended_early_at)}.{" "}
                        {booking.restore_requested_at
                          ? "You asked to restore this booking; Venue staff confirm it."
                          : booking.restore_declined_at
                            ? `Venue staff declined the restore on ${formatInstantDateTime(booking.restore_declined_at)}${
                                booking.restore_decline_reason ? `: ${booking.restore_decline_reason}` : ""
                              }. Ask again, or find a replacement.`
                            : "Ask to restore this booking, or find a replacement."}
                      </span>
                    )}
                    {block && replacement && (
                      <span className="venue-booking-row__hold">
                        Replacement {bookingStatusLabel(replacement.status).toLowerCase()}: {replacement.venue.name} (
                        {replacement.reference}).{" "}
                        {replacement.status === "requested" ? "This booking is replaced once Venue staff approve it." : ""}
                      </span>
                    )}
                    {/* AC 4: the original keeps its details once replaced. */}
                    {booking.status === "replaced" && (
                      <span className="venue-booking-row__decision">
                        Replaced{replacedBy ? ` by ${replacedBy.venue.name} (${replacedBy.reference})` : ""}
                        {booking.replaced_at ? ` on ${formatInstantDateTime(booking.replaced_at)}` : ""}.
                      </span>
                    )}
                    {replaces && <span>Replaces {replaces.reference} at {replaces.venue.name}.</span>}
                  </div>
                  {booking.is_primary && <span className="venue-badge venue-badge--primary">Primary</span>}
                  {needsRearrangement(booking) && (
                    <span className="venue-badge venue-badge--rearrange">Needs rearrangement</span>
                  )}
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
                  {booking.status === "held" && declining !== booking.id && (
                    <>
                      {/* US23a: a hold the venue's unavailability overlaps can't be confirmed, only declined. */}
                      {!needsRearrangement(booking) && (
                        <button
                          type="button"
                          className="request-button request-button--primary"
                          onClick={() => void decideHold(booking, "confirmed")}
                        >
                          Confirm hold
                        </button>
                      )}
                      <button type="button" className="request-button request-button--quiet" onClick={() => setDeclining(booking.id)}>
                        Decline hold
                      </button>
                    </>
                  )}
                  {/* Declining frees the window to anyone at once and can't be undone, so it asks first. */}
                  {booking.status === "held" && declining === booking.id && (
                    <div className="venue-booking-row__confirm" role="group" aria-label="Confirm declining the hold">
                      <span>Decline the hold on {booking.venue.name}? The venue is free for anyone to book at once.</span>
                      <button type="button" className="request-button request-button--quiet" onClick={() => setDeclining(null)}>
                        Keep hold
                      </button>
                      <button
                        type="button"
                        className="request-button request-button--secondary"
                        onClick={() => void decideHold(booking, "declined")}
                      >
                        Decline hold
                      </button>
                    </div>
                  )}
                  {/* US23b (SCRUM-91) AC 2, 5: replace it, or once the period ended early, ask to restore it. */}
                  {block && !replacement && (
                    <button
                      type="button"
                      className="request-button request-button--primary"
                      onClick={() => {
                        setNotice(null);
                        setError(null);
                        setReplacing(booking);
                      }}
                    >
                      Find a replacement
                    </button>
                  )}
                  {block?.ended_early_at && !replacement && !booking.restore_requested_at && (
                    <button
                      type="button"
                      className="request-button request-button--secondary"
                      onClick={() => void requestRestore(booking)}
                    >
                      Ask to restore
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
