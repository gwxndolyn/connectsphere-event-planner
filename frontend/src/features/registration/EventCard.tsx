import type { CampusEvent } from "./types";

const CATEGORY_LABEL: Record<CampusEvent["category"], string> = {
  workshop: "Workshop",
  social: "Social",
  career: "Career",
  performance: "Performance",
};

const CATEGORY_ICON: Record<CampusEvent["category"], string> = {
  workshop: "🛠️",
  social: "🎉",
  career: "💼",
  performance: "🎻",
};

interface EventCardProps {
  event: CampusEvent;
  onReserve: (event: CampusEvent) => void;
}

function badgeFor(event: CampusEvent) {
  const ratio = event.registeredCount / event.capacity;
  if (ratio >= 1) return { label: "Waitlist only", variant: "soon" as const };
  if (ratio >= 0.85) return { label: "Almost full", variant: "hot" as const };
  if (ratio >= 0.6) return { label: "Going fast", variant: "hot" as const };
  return null;
}

export function EventCard({ event, onReserve }: EventCardProps) {
  const seatsLeft = event.capacity - event.registeredCount;
  const isFull = seatsLeft <= 0;
  const badge = badgeFor(event);

  return (
    <button type="button" className="event-card" onClick={() => onReserve(event)}>
      <div className={`event-card__thumb event-card__thumb--${event.category}`}>
        {badge && (
          <span className={`event-card__badge event-card__badge--${badge.variant}`}>
            {badge.label}
          </span>
        )}
        <span className="event-card__icon" aria-hidden="true">
          {CATEGORY_ICON[event.category]}
        </span>
      </div>

      <div className="event-card__body">
        <p className="event-card__category">{CATEGORY_LABEL[event.category]}</p>
        <h3 className="event-card__title">{event.title}</h3>
        <p className="event-card__date">
          {event.date}, {event.time}
        </p>
        <p className="event-card__venue">{event.venue}</p>
        <p className={`event-card__seats${isFull ? " event-card__seats--full" : ""}`}>
          {isFull ? "Waitlist only" : `${seatsLeft} seats left`}
        </p>
      </div>
    </button>
  );
}
