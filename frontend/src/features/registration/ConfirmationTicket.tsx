import { bookingReference } from "./api";
import { formatEventDate, formatEventTimeRange } from "./datetime";
import type { RegistrationConfirmation } from "./types";

interface ConfirmationTicketProps {
  confirmation: RegistrationConfirmation;
  onDone: () => void;
}

/** The register confirmation: event, date, time and venue, as the AC requires (§3). */
export function ConfirmationTicket({ confirmation, onDone }: ConfirmationTicketProps) {
  const { event } = confirmation;

  return (
    <div className="ticket">
      <div className="ticket__icon ticket__icon--registered" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="26" height="26">
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M5 13l4 4L19 7"
          />
        </svg>
      </div>

      <h3 className="ticket__title">You're going!</h3>
      <p className="ticket__event">{event.title}</p>

      <div className="ticket__details">
        <p>{formatEventDate(event)}, {formatEventTimeRange(event)}</p>
        <p>
          {event.joinUrl ? (
            <a href={event.joinUrl} target="_blank" rel="noreferrer">
              Join online
            </a>
          ) : (
            event.venue
          )}
        </p>
      </div>

      <p className="ticket__message">Show this confirmation at the door.</p>

      <div className="ticket__code-row">
        <span>Booking reference</span>
        <span className="ticket__code">{bookingReference(confirmation.registrationId)}</span>
      </div>

      <button type="button" className="button button--secondary ticket__done" onClick={onDone}>
        Back to events
      </button>
    </div>
  );
}
