import type { CampusEvent } from "./types";

const CATEGORY_LABEL: Record<CampusEvent["category"], string> = {
  workshop: "Workshop",
  social: "Social",
  career: "Career",
  performance: "Performance",
};

interface EventCardProps {
  event: CampusEvent;
  onReserve: (event: CampusEvent) => void;
}

export function EventCard({ event, onReserve }: EventCardProps) {
  const seatsLeft = event.capacity - event.registeredCount;
  const isFull = seatsLeft <= 0;

  return (
    <article className={`event-card event-card--${event.category}`}>
      <p className="event-card__category">{CATEGORY_LABEL[event.category]}</p>
      <h3 className="event-card__title">{event.title}</h3>
      <p className="event-card__description">{event.description}</p>

      <div className="event-card__rule" aria-hidden="true" />

      <p className="event-card__meta">
        {event.date}, {event.time}
      </p>
      <p className="event-card__meta">{event.venue}</p>

      <div className="event-card__footer">
        <p className={`event-card__seats${isFull ? " event-card__seats--full" : ""}`}>
          {isFull ? "Full" : `${seatsLeft} of ${event.capacity} seats left`}
        </p>
        <button
          type="button"
          className={isFull ? "button button--waitlist" : "button button--reserve"}
          onClick={() => onReserve(event)}
        >
          {isFull ? "Join the waitlist" : "Reserve my seat"}
        </button>
      </div>
    </article>
  );
}
