import { useMemo, useState } from "react";
import { registrationErrorMessage } from "./api";
import { EventCard } from "./EventCard";
import "./registration.css";
import { RegistrationDialog } from "./RegistrationDialog";
import type { useEventRegistry } from "./useEventRegistry";

type Tab = "all" | "open" | "full";

const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "open", label: "Open" },
  { id: "full", label: "Full" },
];

interface EventsBoardProps {
  registry: ReturnType<typeof useEventRegistry>;
  search: string;
}

export function EventsBoard({ registry, search }: EventsBoardProps) {
  const { events, myRegistrations, loading, error, register } = registry;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("all");

  // Looked up by id so the dialog sees fresh seat counts after each refresh.
  const selectedEvent = selectedId ? events.find((e) => e.id === selectedId) ?? null : null;

  // `already_registered` is true for waitlisted rows too, so the board tells them apart by event id.
  const waitlistPositions = useMemo(
    () => new Map(myRegistrations.waitlisted.map((row) => [row.eventId, row.waitlistPosition])),
    [myRegistrations],
  );

  // The API returns only events open for registration that haven't ended, soonest first.
  const visibleEvents = useMemo(() => {
    const query = search.trim().toLowerCase();
    return events.filter((event) => {
      if (tab === "open" && event.isFull) return false;
      if (tab === "full" && !event.isFull) return false;

      if (!query) return true;
      return (
        event.title.toLowerCase().includes(query) || (event.venue ?? "").toLowerCase().includes(query)
      );
    });
  }, [events, search, tab]);

  return (
    <section className="board">
      <h1 className="board__title">Events at ConnectSphere</h1>

      <nav className="board__tabs">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`board__tab${tab === id ? " board__tab--active" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {loading ? (
        <p className="board__empty" role="status">
          Loading events…
        </p>
      ) : error ? (
        <p className="board__empty board__error" role="alert">
          {registrationErrorMessage(error)}
        </p>
      ) : visibleEvents.length === 0 ? (
        <p className="board__empty">
          {search.trim() ? `No events match "${search}". Try another search.` : "No events are open for registration right now."}
        </p>
      ) : (
        <div className="board__grid">
          {visibleEvents.map((event) => (
            <EventCard
              key={event.id}
              event={event}
              waitlisted={waitlistPositions.has(event.id)}
              waitlistPosition={waitlistPositions.get(event.id)}
              onReserve={(chosen) => setSelectedId(chosen.id)}
            />
          ))}
        </div>
      )}

      {selectedEvent && (
        <RegistrationDialog
          event={selectedEvent}
          waitlisted={waitlistPositions.has(selectedEvent.id)}
          onRegister={(answers) => register(selectedEvent.id, answers)}
          onClose={() => setSelectedId(null)}
        />
      )}
    </section>
  );
}
