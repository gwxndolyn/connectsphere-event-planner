import { useId } from "react";
import { allocationText, venuesMissing } from "./bookingApi";
import type { EventVenues } from "./bookingTypes";
import "./venues.css";

interface VenueArrangementsProps {
  venues: EventVenues;
  // The coordinator acts on what's missing; the Organiser only reads it.
  audience: "coordinator" | "organiser";
}

/**
 * US24 AC 3, 7 (D67, D72): the event's allocations against its expected attendance, whether its venues
 * are arranged, and if not, what's missing. Shared by the coordinator's panel and the Organiser's view.
 */
export function VenueArrangements({ venues, audience }: VenueArrangementsProps) {
  const titleId = useId();
  const missing = venuesMissing(venues, audience);
  return (
    <section className="venue-arrangements" aria-labelledby={titleId}>
      <h3 id={titleId} className="venue-arrangements__title">
        Venue arrangements
      </h3>
      <p className={venues.venues_arranged ? "venue-arrangements__done" : "venue-arrangements__pending"}>
        {venues.venues_arranged ? "Venues arranged" : "Venues not arranged"}
      </p>
      <p className="venue-arrangements__allocation">{allocationText(venues)}</p>
      {missing.length > 0 && (
        <ul className="venue-arrangements__missing" aria-label="What's missing">
          {missing.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
