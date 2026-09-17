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
      <div className="ticket__main">
        <p className={`ticket__stamp ticket__stamp--${variant}`}>
          {isRegistered ? "Confirmed" : "Waitlisted"}
        </p>
        <h3 className="ticket__title">{event.title}</h3>
        {attendeeName && <p className="ticket__attendee">{attendeeName}</p>}

        <div className="ticket__details">
          <p>{event.date}, {event.time}</p>
          <p>{event.venue}</p>
        </div>

        <p className="ticket__message">
          {isRegistered
            ? "You're on the list — show this confirmation at the door."
            : `The event is full. We'll email ${email} the moment a seat opens up.`}
        </p>
      </div>

      {isRegistered && (
        <div className="ticket__stub">
          <p className="ticket__stub-label">Confirmation</p>
          <p className="ticket__code">{confirmationCode}</p>
        </div>
      )}

      <button type="button" className="button button--secondary ticket__done" onClick={onDone}>
        Back to events
      </button>
    </div>
  );
}
