import { useState } from "react";
import { EventCard } from "./EventCard";
import { mockEvents } from "./mockEvents";
import "./registration.css";
import { RegistrationDialog } from "./RegistrationDialog";
import type { CampusEvent } from "./types";
import { useRegistrationBoard } from "./useRegistrationBoard";

export function EventsBoard() {
  const { events, register, joinWaitlist } = useRegistrationBoard(mockEvents);
  const [selected, setSelected] = useState<CampusEvent | null>(null);

  const selectedEvent = selected ? events.find((e) => e.id === selected.id) ?? null : null;

  return (
    <section className="board">
      <header className="board__header">
        <h1 className="board__title">Campus Events</h1>
        <p className="board__subtitle">Confirmed events open for registration this month.</p>
      </header>

      <div className="board__grid">
        {events.map((event) => (
          <EventCard key={event.id} event={event} onReserve={setSelected} />
        ))}
      </div>

      {selectedEvent && (
        <RegistrationDialog
          event={selectedEvent}
          onRegister={(name, email) => register(selectedEvent.id, { name, email })}
          onJoinWaitlist={(email) => joinWaitlist(selectedEvent.id, email)}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}
