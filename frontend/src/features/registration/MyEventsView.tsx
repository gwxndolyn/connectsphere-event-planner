import { useState } from "react";
import { AcceptOfferDialog } from "./AcceptOfferDialog";
import { registrationErrorMessage } from "./api";
import { formatEventDate, formatEventTimeRange, formatInstantDateTime, toTimed } from "./datetime";
import type { MyRegistration } from "./types";
import type { useEventRegistry } from "./useEventRegistry";
import { WithdrawDialog } from "./WithdrawDialog";

interface MyEventsViewProps {
  registry: ReturnType<typeof useEventRegistry>;
  onBrowse: () => void;
}

/**
 * The attendee's upcoming registrations, from `GET /me/registrations` (SCRUM-30/31): already
 * split into sections, sorted by start time and without ended events. A place offered after a
 * withdrawal (US6b) comes first, with "Accept place" (SCRUM-76). An offer that lapsed comes last,
 * muted, so its holder sees it expired rather than vanish (SCRUM-137).
 */
export function MyEventsView({ registry, onBrowse }: MyEventsViewProps) {
  const { myRegistrations, loading, error, withdraw, acceptOffer } = registry;
  // Held separately from the registry: the row is gone once the withdrawal goes through,
  // but the confirmation still needs it to describe what happened.
  const [pending, setPending] = useState<MyRegistration | null>(null);
  // Same reason: once accepted, the row moves from Place available to Confirmed.
  const [accepting, setAccepting] = useState<MyRegistration | null>(null);
  const { confirmed, waitlisted, offered, expired } = myRegistrations;

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
      ) : confirmed.length + waitlisted.length + offered.length + expired.length === 0 ? (
        <div className="my-events__empty">
          <p>You haven't registered for any upcoming events yet.</p>
          <button type="button" className="button button--reserve" onClick={onBrowse}>
            Browse events
          </button>
        </div>
      ) : (
        <>
          {offered.length > 0 && <OfferedSection registrations={offered} onAccept={setAccepting} />}

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

          {expired.length > 0 && <ExpiredSection registrations={expired} />}
        </>
      )}

      {accepting && (
        <AcceptOfferDialog
          registration={accepting}
          onConfirm={() => acceptOffer(accepting.id)}
          onClose={() => setAccepting(null)}
        />
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

interface OfferedSectionProps {
  registrations: MyRegistration[];
  onAccept: (registration: MyRegistration) => void;
}

/** US6b AC 1–2: the next attendee in the queue sees the freed place, and until when it's held. */
function OfferedSection({ registrations, onAccept }: OfferedSectionProps) {
  return (
    <div className="my-events__section my-events__section--offered">
      <h2 className="my-events__heading">Place available</h2>
      <ul className="my-events__list">
        {registrations.map((registration) => {
          const timed = toTimed(registration.date, registration.startTime, registration.endTime);
          return (
            <li key={registration.id} className="my-events__row my-events__row--offered">
              <div className="my-events__info">
                <p className="my-events__event-title">{registration.eventTitle}</p>
                <p className="my-events__event-meta">
                  {formatEventDate(timed)}, {formatEventTimeRange(timed)}
                </p>
                {registration.offerExpiresAt && (
                  <p className="my-events__offer">
                    A seat opened up for you. Held until {formatInstantDateTime(registration.offerExpiresAt)}.
                  </p>
                )}
              </div>
              <button type="button" className="button button--reserve" onClick={() => onAccept(registration)}>
                Accept place
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** SCRUM-137 (TC-US7-22): an offer the holder didn't take up in time. The place has gone to the next
 * person or back to the event, so there's nothing to press. */
function ExpiredSection({ registrations }: { registrations: MyRegistration[] }) {
  return (
    <div className="my-events__section">
      <h2 className="my-events__heading">Offer expired</h2>
      <ul className="my-events__list">
        {registrations.map((registration) => {
          const timed = toTimed(registration.date, registration.startTime, registration.endTime);
          return (
            <li key={registration.id} className="my-events__row my-events__row--expired">
              <div className="my-events__info">
                <p className="my-events__event-title">{registration.eventTitle}</p>
                <p className="my-events__event-meta">
                  {formatEventDate(timed)}, {formatEventTimeRange(timed)}
                </p>
                {registration.offerExpiresAt && (
                  <p className="my-events__expired-note">
                    Your offer expired at {formatInstantDateTime(registration.offerExpiresAt)}; the place has moved on.
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
