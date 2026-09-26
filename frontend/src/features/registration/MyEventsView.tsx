import { useState } from "react";
import { compareEventStart, formatEventDate, formatEventTimeRange, isEventExpired } from "./datetime";
import type { EventAvailability, Registration } from "./types";
import type { useEventRegistry } from "./useEventRegistry";
import { WithdrawDialog } from "./WithdrawDialog";

interface MyEventsViewProps {
  registry: ReturnType<typeof useEventRegistry>;
  onBrowse: () => void;
}

interface Entry {
  registration: Registration;
  event: EventAvailability;
}

export function MyEventsView({ registry, onBrowse }: MyEventsViewProps) {
  const { events, registrations, currentAttendee, cancelRegistration, waitlistPosition } = registry;
  // Held separately from the registry: the row is gone once the withdrawal goes through,
  // but the confirmation still needs the event and registration to describe what happened.
  const [pending, setPending] = useState<Entry | null>(null);

  const myEntries: Entry[] = currentAttendee
    ? registrations
        .filter((r) => r.attendee.email === currentAttendee.email)
        .map((registration) => {
          const event = events.find((e) => e.id === registration.eventId);
          return event ? { registration, event } : null;
        })
        .filter((entry): entry is Entry => entry !== null && !isEventExpired(entry.event))
    : [];

  const confirmed = myEntries
    .filter((e) => e.registration.status === "confirmed")
    .sort((a, b) => compareEventStart(a.event, b.event));
  const waitlisted = myEntries
    .filter((e) => e.registration.status === "waitlisted")
    .sort((a, b) => compareEventStart(a.event, b.event));

  return (
    <section className="board">
      <h1 className="board__title">My events</h1>

      {myEntries.length === 0 ? (
        <div className="my-events__empty">
          <p>You haven't registered for any upcoming events yet.</p>
          <button type="button" className="button button--reserve" onClick={onBrowse}>
            Browse events
          </button>
        </div>
      ) : (
        <>
          {confirmed.length > 0 && (
            <MyEventsSection
              heading="Confirmed"
              entries={confirmed}
              onCancel={setPending}
              cancelLabel="Cancel registration"
            />
          )}

          {waitlisted.length > 0 && (
            <MyEventsSection
              heading="Waitlisted"
              entries={waitlisted}
              onCancel={setPending}
              cancelLabel="Leave waitlist"
              waitlistPosition={waitlistPosition}
            />
          )}
        </>
      )}

      {pending && (
        <WithdrawDialog
          event={pending.event}
          registration={pending.registration}
          waitlistPosition={
            pending.registration.status === "waitlisted"
              ? waitlistPosition(pending.registration)
              : undefined
          }
          onConfirm={() => cancelRegistration(pending.registration.id)}
          onClose={() => setPending(null)}
        />
      )}
    </section>
  );
}

interface MyEventsSectionProps {
  heading: string;
  entries: Entry[];
  onCancel: (entry: Entry) => void;
  cancelLabel: string;
  waitlistPosition?: (registration: Registration) => number;
}

function MyEventsSection({
  heading,
  entries,
  onCancel,
  cancelLabel,
  waitlistPosition,
}: MyEventsSectionProps) {
  return (
    <div className="my-events__section">
      <h2 className="my-events__heading">{heading}</h2>
      <ul className="my-events__list">
        {entries.map(({ registration, event }) => (
          <li key={registration.id} className="my-events__row">
            <div className="my-events__info">
              <p className="my-events__event-title">{event.title}</p>
              <p className="my-events__event-meta">
                {formatEventDate(event)}, {formatEventTimeRange(event)}
              </p>
              <p className="my-events__event-meta">
                {event.format === "online" ? (
                  <a href={event.joinUrl} target="_blank" rel="noreferrer">
                    Join online
                  </a>
                ) : (
                  event.venue
                )}
              </p>
              {waitlistPosition && (
                <p className="my-events__position">
                  Position {waitlistPosition(registration)} on the waitlist
                </p>
              )}
            </div>
            <button
              type="button"
              className="button button--secondary"
              onClick={() => onCancel({ registration, event })}
            >
              {cancelLabel}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
