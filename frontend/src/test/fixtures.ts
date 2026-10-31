import { vi } from "vitest";
import type { EventAvailability, MyRegistration, MyRegistrations } from "../features/registration/types";
import type { useEventRegistry } from "../features/registration/useEventRegistry";

type Registry = ReturnType<typeof useEventRegistry>;

/** An open in-person event with seats left, in the shape `registrationApi.listAvailable` returns. */
export function makeEvent(overrides: Partial<EventAvailability> = {}): EventAvailability {
  return {
    id: "event-1",
    title: "Tech Talk: Agile at Scale",
    format: "in-person",
    startsAt: "2026-10-02T14:00:00+08:00",
    endsAt: "2026-10-02T16:00:00+08:00",
    venue: "SMU SCIS Building",
    capacity: 40,
    seatsRemaining: 38,
    isFull: false,
    waitlistAvailable: false,
    alreadyRegistered: false,
    registrationFields: [],
    ...overrides,
  };
}

/** A confirmed in-person row of My events. */
export function makeRegistration(overrides: Partial<MyRegistration> = {}): MyRegistration {
  return {
    id: "registration-1",
    eventId: "event-1",
    status: "confirmed",
    eventTitle: "Tech Talk: Agile at Scale",
    date: "2026-10-02",
    startTime: "14:00",
    endTime: "16:00",
    format: "in-person",
    venue: "SMU SCIS Building",
    joiningInfo: "Seminar Room 2-1",
    ...overrides,
  };
}

/** A loaded registry with no events or registrations; every action is a mock. */
export function makeRegistry(
  overrides: Partial<Omit<Registry, "myRegistrations">> & { myRegistrations?: Partial<MyRegistrations> } = {},
): Registry {
  const { myRegistrations, ...rest } = overrides;
  return {
    events: [],
    loading: false,
    error: null,
    refresh: vi.fn().mockResolvedValue(undefined),
    register: vi.fn(),
    joinWaitlist: vi.fn(),
    acceptOffer: vi.fn(),
    withdraw: vi.fn(),
    ...rest,
    myRegistrations: { confirmed: [], waitlisted: [], offered: [], expired: [], ...myRegistrations },
  };
}
