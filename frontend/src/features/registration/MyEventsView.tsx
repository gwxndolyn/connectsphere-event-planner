import { useState } from "react";
import { registrationErrorMessage } from "./api";
import { formatEventDate, formatEventTimeRange, toTimed } from "./datetime";
import type { MyRegistration } from "./types";
import type { useEventRegistry } from "./useEventRegistry";
import { WithdrawDialog } from "./WithdrawDialog";

interface MyEventsViewProps {
  registry: ReturnType<typeof useEventRegistry>;
  onBrowse: () => void;
}

/**
 * The attendee's upcoming registrations, from `GET /me/registrations` (SCRUM-30/31): already
 * split into sections, sorted by start time and without ended events. `offered` rows are kept in
 * the registry but not shown until SCRUM-76 adds "Accept place".
 */
export function MyEventsView({ registry, onBrowse }: MyEventsViewProps) {
  const { myRegistrations, loading, error, withdraw } = registry;
  // Held separately from the registry: the row is gone once the withdrawal goes through,
  // but the confirmation still needs it to describe what happened.
  const [pending, setPending] = useState<MyRegistration | null>(null);
  const { confirmed, waitlisted } = myRegistrations;

  return (
    <section className="board">
      <h1 className="board__title">My events</h1>

      {loading ? (
        <p className="board__empty" role="status">
          Loading your events…
        </p>
      ) : error ? (
        <p className="board__empty" role="alert">
          {registrationErrorMessage(error)}
        </p>
      ) : confirmed.length + waitlisted.length === 0 ? (
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
              registrations={confirmed}
              onCancel={setPending}
              cancelLabel="Cancel registration"
            />
          )}

          {waitlisted.length > 0 && (
            <MyEventsSection
              heading="Waitlisted"
              registrations={waitlisted}
              onCancel={setPending}
              cancelLabel="Leave waitlist"
            />
          )}
        </>
      )}

      {pending && (
        <WithdrawDialog
          registration={pending}
          onConfirm={() => withdraw(pending.id)}
          onClose={() => setPending(null)}
        />
      )}
    </section>
  );
}

interface MyEventsSectionProps {
  heading: string;
  registrations: MyRegistration[];
  onCancel: (registration: MyRegistration) => void;
  cancelLabel: string;
}

function MyEventsSection({ heading, registrations, onCancel, cancelLabel }: MyEventsSectionProps) {
  return (
    <div className="my-events__section">
      <h2 className="my-events__heading">{heading}</h2>
      <ul className="my-events__list">
        {registrations.map((registration) => {
          const timed = toTimed(registration.date, registration.startTime, registration.endTime);
          return (
            <li key={registration.id} className="my-events__row">
              <div className="my-events__info">
                <p className="my-events__event-title">{registration.eventTitle}</p>
                <p className="my-events__event-meta">
                  {formatEventDate(timed)}, {formatEventTimeRange(timed)}
                </p>
                <p className="my-events__event-meta">
                  {registration.format === "online" ? (
                    <a href={registration.joiningInfo} target="_blank" rel="noreferrer">
                      Join online
                    </a>
                  ) : (
                    [registration.venue, registration.joiningInfo].filter(Boolean).join(" · ")
                  )}
                </p>
                {registration.waitlistPosition !== undefined && (
                  <p className="my-events__position">
                    Position {registration.waitlistPosition} on the waitlist
                  </p>
                )}
              </div>
              <button
                type="button"
                className="button button--secondary"
                onClick={() => onCancel(registration)}
              >
                {cancelLabel}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
