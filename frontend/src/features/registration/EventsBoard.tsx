import { useMemo, useState } from "react";
import { isEventExpired } from "./datetime";
import { EventCard } from "./EventCard";
import "./registration.css";
import { RegistrationDialog } from "./RegistrationDialog";
import type { EventAvailability } from "./types";
import type { useEventRegistry } from "./useEventRegistry";

type Tab = "all" | "open" | "waitlist";

const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "open", label: "Open" },
  { id: "waitlist", label: "Waitlist only" },
];

interface EventsBoardProps {
  registry: ReturnType<typeof useEventRegistry>;
  search: string;
}

export function EventsBoard({ registry, search }: EventsBoardProps) {
  const { events, currentAttendee, register, joinWaitlist } = registry;
  const [selected, setSelected] = useState<EventAvailability | null>(null);
  const [tab, setTab] = useState<Tab>("all");

  const selectedEvent = selected ? events.find((e) => e.id === selected.id) ?? null : null;

  const visibleEvents = useMemo(() => {
    const query = search.trim().toLowerCase();
    return events.filter((event) => {
      if (isEventExpired(event)) return false;

      const isFull = event.registeredCount >= event.capacity;
      if (tab === "open" && isFull) return false;
      if (tab === "waitlist" && !isFull) return false;

      if (!query) return true;
      return (
        event.title.toLowerCase().includes(query) ||
        (event.venue ?? "").toLowerCase().includes(query) ||
        event.category.toLowerCase().includes(query)
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

      {visibleEvents.length === 0 ? (
        <p className="board__empty">No events match "{search}". Try another search.</p>
      ) : (
        <div className="board__grid">
          {visibleEvents.map((event) => (
            <EventCard key={event.id} event={event} onReserve={setSelected} />
          ))}
        </div>
      )}

      {selectedEvent && (
        <RegistrationDialog
          event={selectedEvent}
          currentAttendee={currentAttendee}
          onRegister={(name, email) => register(selectedEvent.id, { name, email })}
          onJoinWaitlist={(email) => joinWaitlist(selectedEvent.id, email)}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
