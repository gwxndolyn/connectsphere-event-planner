import { useMemo, useState } from "react";
import { SiteHeader } from "../../components/SiteHeader";
import { EventCard } from "./EventCard";
import { mockEvents } from "./mockEvents";
import "./registration.css";
import { RegistrationDialog } from "./RegistrationDialog";
import type { CampusEvent } from "./types";
import { useRegistrationBoard } from "./useRegistrationBoard";

type Tab = "all" | "open" | "waitlist";

const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "open", label: "Open" },
  { id: "waitlist", label: "Waitlist only" },
];

export function EventsBoard() {
  const { events, register, joinWaitlist } = useRegistrationBoard(mockEvents);
  const [selected, setSelected] = useState<CampusEvent | null>(null);
  const [search, setSearch] = useState("");
  const [tab, setTab] = useState<Tab>("all");

  const selectedEvent = selected ? events.find((e) => e.id === selected.id) ?? null : null;

  const visibleEvents = useMemo(() => {
    const query = search.trim().toLowerCase();
    return events.filter((event) => {
      const isFull = event.registeredCount >= event.capacity;
      if (tab === "open" && isFull) return false;
      if (tab === "waitlist" && !isFull) return false;

      if (!query) return true;
      return (
        event.title.toLowerCase().includes(query) ||
        event.venue.toLowerCase().includes(query) ||
        event.category.toLowerCase().includes(query)
      );
    });
  }, [events, search, tab]);

  return (
    <>
      <SiteHeader search={search} onSearchChange={setSearch} />

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
      </section>

      {selectedEvent && (
        <RegistrationDialog
          event={selectedEvent}
          onRegister={(name, email) => register(selectedEvent.id, { name, email })}
          onJoinWaitlist={(email) => joinWaitlist(selectedEvent.id, email)}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
