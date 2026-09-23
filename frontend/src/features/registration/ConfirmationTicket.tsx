import { formatEventDate, formatEventTimeRange } from "./datetime";
import type { CampusEvent } from "./types";

interface ConfirmationTicketProps {
  event: CampusEvent;
  variant: "registered" | "waitlisted";
  attendeeName?: string;
  email: string;
  confirmationCode?: string;
  onDone: () => void;
}

export function ConfirmationTicket({
  event,
  variant,
  attendeeName,
  email,
  confirmationCode,
  onDone,
}: ConfirmationTicketProps) {
  const isRegistered = variant === "registered";

  return (
    <div className="ticket">
      <div className={`ticket__icon ticket__icon--${variant}`} aria-hidden="true">
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
            <path
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              d="M12 7v6l4 2"
            />
            <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" />
          </svg>
        )}
      </div>

      <h3 className="ticket__title">
        {isRegistered ? "You're going!" : "You're on the waitlist"}
      </h3>
      <p className="ticket__event">{event.title}</p>
      {attendeeName && <p className="ticket__attendee">{attendeeName}</p>}

      <div className="ticket__details">
        <p>{formatEventDate(event)}, {formatEventTimeRange(event)}</p>
        <p>{event.format === "online" ? "Online" : event.venue}</p>
      </div>

      <p className="ticket__message">
        {isRegistered
          ? "Show this confirmation at the door."
          : `The event is full. We'll email ${email} the moment a seat opens up.`}
      </p>

      {isRegistered && confirmationCode && (
        <div className="ticket__code-row">
          <span>Confirmation code</span>
          <span className="ticket__code">{confirmationCode}</span>
        </div>
      )}

      <button type="button" className="button button--secondary ticket__done" onClick={onDone}>
        Back to events
      </button>
    </div>
  );
}
