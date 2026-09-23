import { useState } from "react";
import type { Attendee, CampusEvent, RegistrationResult } from "./types";

function generateConfirmationCode(): string {
  return `CS-${Math.random().toString(36).slice(2, 7).toUpperCase()}`;
}

/**
 * Mocks the register/waitlist-join endpoints from SCRUM-26/27 so the UI can be
 * built ahead of the backend. Swap the bodies of register/joinWaitlist for
 * apiClient calls once those endpoints exist — the signatures already match.
 */
export function useRegistrationBoard(initialEvents: CampusEvent[]) {
  const [events, setEvents] = useState(initialEvents);
  const [registrations] = useState(() => new Map<string, Set<string>>());
  const [waitlists] = useState(() => new Map<string, Set<string>>());

  function register(eventId: string, attendee: Attendee): RegistrationResult {
    const event = events.find((e) => e.id === eventId);
    if (!event) throw new Error(`Unknown event: ${eventId}`);

    const registered = registrations.get(eventId) ?? new Set<string>();
    const waitlisted = waitlists.get(eventId) ?? new Set<string>();
    if (registered.has(attendee.email) || waitlisted.has(attendee.email)) {
      return { status: "duplicate" };
    }

    if (event.registeredCount >= event.capacity) {
      waitlisted.add(attendee.email);
      waitlists.set(eventId, waitlisted);
      return { status: "waitlisted" };
    }

    registered.add(attendee.email);
    registrations.set(eventId, registered);
    setEvents((prev) =>
      prev.map((e) => (e.id === eventId ? { ...e, registeredCount: e.registeredCount + 1 } : e)),
    );
    return { status: "registered", confirmationCode: generateConfirmationCode() };
  }

  function joinWaitlist(eventId: string, email: string): RegistrationResult {
    const registered = registrations.get(eventId) ?? new Set<string>();
    const waitlisted = waitlists.get(eventId) ?? new Set<string>();
    if (registered.has(email) || waitlisted.has(email)) {
      return { status: "duplicate" };
    }

    waitlisted.add(email);
    waitlists.set(eventId, waitlisted);
    return { status: "waitlisted" };
  }

  return { events, register, joinWaitlist };
}
