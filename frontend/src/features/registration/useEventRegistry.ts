import { useEffect, useMemo, useState } from "react";
import type {
  Attendee,
  CampusEvent,
  EventAvailability,
  Registration,
  RegistrationResult,
} from "./types";

const REGISTRATIONS_KEY = "connectsphere.registrations";
const ATTENDEE_KEY = "connectsphere.attendee";

function generateConfirmationCode(): string {
  return `CS-${Math.random().toString(36).slice(2, 7).toUpperCase()}`;
}

function readJSON<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJSON(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable (private browsing, quota) — registrations just won't persist.
  }
}

/**
 * Mocks the registrations backend (SCRUM-26/27/30/31) so the UI can be built
 * ahead of it. Swap register/joinWaitlist/cancelRegistration for apiClient
 * calls once those endpoints exist — the signatures already match.
 */
export function useEventRegistry(initialEvents: CampusEvent[]) {
  const [registrations, setRegistrations] = useState<Registration[]>(() =>
    readJSON(REGISTRATIONS_KEY, []),
  );
  const [currentAttendee, setCurrentAttendee] = useState<Attendee | null>(() =>
    readJSON(ATTENDEE_KEY, null),
  );

  useEffect(() => writeJSON(REGISTRATIONS_KEY, registrations), [registrations]);
  useEffect(() => writeJSON(ATTENDEE_KEY, currentAttendee), [currentAttendee]);

  const events: EventAvailability[] = useMemo(
    () =>
      initialEvents.map((event) => {
        const confirmedCount = registrations.filter(
          (r) => r.eventId === event.id && r.status === "confirmed",
        ).length;
        return { ...event, registeredCount: event.seedRegisteredCount + confirmedCount };
      }),
    [initialEvents, registrations],
  );

  function hasExistingRegistration(eventId: string, email: string) {
    return registrations.some((r) => r.eventId === eventId && r.attendee.email === email);
  }

  function register(eventId: string, attendee: Attendee): RegistrationResult {
    const event = events.find((e) => e.id === eventId);
    if (!event) throw new Error(`Unknown event: ${eventId}`);
    if (hasExistingRegistration(eventId, attendee.email)) return { status: "duplicate" };

    setCurrentAttendee(attendee);

    if (event.registeredCount >= event.capacity) {
      setRegistrations((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          eventId,
          attendee,
          status: "waitlisted",
          registeredAt: new Date().toISOString(),
        },
      ]);
      return { status: "waitlisted" };
    }

    const confirmationCode = generateConfirmationCode();
    setRegistrations((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        eventId,
        attendee,
        status: "confirmed",
        confirmationCode,
        registeredAt: new Date().toISOString(),
      },
    ]);
    return { status: "registered", confirmationCode };
  }

  function joinWaitlist(eventId: string, email: string): RegistrationResult {
    if (hasExistingRegistration(eventId, email)) return { status: "duplicate" };

    setCurrentAttendee((prev) => prev ?? { name: "", email });
    setRegistrations((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        eventId,
        attendee: { name: "", email },
        status: "waitlisted",
        registeredAt: new Date().toISOString(),
      },
    ]);
    return { status: "waitlisted" };
  }

  function cancelRegistration(registrationId: string) {
    setRegistrations((prev) => prev.filter((r) => r.id !== registrationId));
  }

  function waitlistPosition(registration: Registration): number {
    const event = initialEvents.find((e) => e.id === registration.eventId);
    const seedAhead = event?.seedWaitlistCount ?? 0;
    const aheadInQueue = registrations.filter(
      (r) =>
        r.eventId === registration.eventId &&
        r.status === "waitlisted" &&
        r.registeredAt < registration.registeredAt,
    ).length;
    return seedAhead + aheadInQueue + 1;
  }

  return {
    events,
    registrations,
    currentAttendee,
    register,
    joinWaitlist,
    cancelRegistration,
    waitlistPosition,
  };
}
