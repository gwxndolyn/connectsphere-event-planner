import { bookingReference } from "./api";
import { formatEventDate, formatEventTimeRange } from "./datetime";
import type { ConfirmedEvent } from "./types";

type ConfirmationTicketProps = {
  event: ConfirmedEvent;
  onDone: () => void;
} & (
  | { variant: "registered"; registrationId: string }
  // US6a AC 3: joining a waitlist is confirmed with the position.
  | { variant: "waitlisted"; position: number }
);

/** The register confirmation (event, date, time and venue, per the AC, §3) or the waitlist one. */
export function ConfirmationTicket(props: ConfirmationTicketProps) {
  const { event, onDone } = props;
  const isRegistered = props.variant === "registered";

  return (
    <div className="ticket">
      <div className={`ticket__icon ticket__icon--${props.variant}`} aria-hidden="true">
        {isRegistered ? (
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
        ) : (
          <svg viewBox="0 0 24 24" width="24" height="24">
            <path fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" d="M12 7v6l4 2" />
            <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" />
          </svg>
        )}
      </div>

      <h3 className="ticket__title">{isRegistered ? "You're going!" : "You're on the waitlist"}</h3>
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

      <p className="ticket__message">
        {isRegistered
          ? "Show this confirmation at the door."
          : "If a seat opens up, it's offered to the next person in line. Offers appear under My events."}
      </p>

      <div className="ticket__code-row">
        {props.variant === "registered" ? (
          <>
            <span>Booking reference</span>
            <span className="ticket__code">{bookingReference(props.registrationId)}</span>
          </>
        ) : (
          <>
            <span>Your place</span>
            <span className="ticket__code">You're #{props.position} in the queue</span>
          </>
        )}
      </div>

      <button type="button" className="button button--secondary ticket__done" onClick={onDone}>
        Back to events
      </button>
    </div>
  );
}
