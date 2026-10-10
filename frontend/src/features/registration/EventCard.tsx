import { formatEventDate, formatEventTime } from "./datetime";
import type { EventAvailability } from "./types";

interface EventCardProps {
  event: EventAvailability;
  waitlisted: boolean;
  waitlistPosition?: number;
  onReserve: (event: EventAvailability) => void;
}

function badgeFor(event: EventAvailability) {
  if (event.isFull) return { label: "Full", variant: "soon" as const };
  const ratio = event.capacity > 0 ? (event.capacity - event.seatsRemaining) / event.capacity : 1;
  if (ratio >= 0.85) return { label: "Almost full", variant: "hot" as const };
  if (ratio >= 0.6) return { label: "Going fast", variant: "hot" as const };
  return null;
}

function seatsText(event: EventAvailability, waitlisted: boolean, waitlistPosition?: number): string {
  if (waitlisted) return waitlistPosition ? `You're on the waitlist (#${waitlistPosition})` : "You're on the waitlist";
  if (event.alreadyRegistered) return "You're registered";
  // US6a AC 3: a full event without a waitlist offers nothing, so the board tells them apart.
  if (event.isFull) return event.waitlistAvailable ? "Full · waitlist open" : "Full";
  return `${event.seatsRemaining} ${event.seatsRemaining === 1 ? "seat" : "seats"} left`;
}

export function EventCard({ event, waitlisted, waitlistPosition, onReserve }: EventCardProps) {
  const badge = badgeFor(event);

  return (
    <button type="button" className="event-card" onClick={() => onReserve(event)}>
      <div className="event-card__thumb event-card__thumb--default">
        {badge && (
          <span className={`event-card__badge event-card__badge--${badge.variant}`}>
            {badge.label}
          </span>
        )}
      </div>

      <div className="event-card__body">
        <h3 className="event-card__title">{event.title}</h3>
        <p className="event-card__date">
          {formatEventDate(event)}, {formatEventTime(event)}
        </p>
        <p className="event-card__venue">
          {event.format === "online" ? "Online" : event.venue}
        </p>
        <p
          className={`event-card__seats${event.isFull && !event.alreadyRegistered ? " event-card__seats--full" : ""}${
            event.alreadyRegistered ? " event-card__seats--registered" : ""
          }`}
        >
          {seatsText(event, waitlisted, waitlistPosition)}
        </p>
      </div>
    </button>
  );
}
