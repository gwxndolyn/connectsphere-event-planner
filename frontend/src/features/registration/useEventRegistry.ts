import { useCallback, useEffect, useState } from "react";
import { registrationApi } from "./api";
import type {
  EventAvailability,
  MyRegistrations,
  RegistrationConfirmation,
  WaitlistConfirmation,
  WithdrawalResult,
} from "./types";

const NO_REGISTRATIONS: MyRegistrations = { confirmed: [], waitlisted: [], offered: [] };

function loadBoth() {
  return Promise.all([registrationApi.listAvailable(), registrationApi.listMine()]);
}

/**
 * The attendee's view of events and registrations, from the API (SCRUM-79): the events board
 * (SCRUM-25), register (SCRUM-26), My Events (SCRUM-30/31) and withdraw (SCRUM-34). Both lists
 * are re-read after every change, so seat counts and sections always match the server.
 *
 * Joining a waitlist (SCRUM-52) and accepting an offer (SCRUM-76) work the same way: call
 * `registrationApi`, then `refresh()`.
 *
 * `enabled` is false for a logged-in staff user, who has no attendee screens, so the attendee routes
 * are never called with their token (SCRUM-105).
 */
export function useEventRegistry(enabled = true) {
  const [events, setEvents] = useState<EventAvailability[]>([]);
  const [myRegistrations, setMyRegistrations] = useState<MyRegistrations>(NO_REGISTRATIONS);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<unknown>(null);

  const applyLoad = useCallback((isCurrent: () => boolean = () => true) => {
    return loadBoth()
      .then(([available, mine]) => {
        if (!isCurrent()) return;
        setEvents(available);
        setMyRegistrations(mine);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (isCurrent()) setError(reason);
      })
      .finally(() => {
        if (isCurrent()) setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let current = true;
    void applyLoad(() => current);
    return () => {
      current = false;
    };
  }, [applyLoad, enabled]);

  const refresh = useCallback(() => applyLoad(), [applyLoad]);

  async function register(eventId: string, answers: Record<string, string>): Promise<RegistrationConfirmation> {
    const confirmation = await registrationApi.register(eventId, answers);
    await refresh();
    return confirmation;
  }

  async function joinWaitlist(eventId: string): Promise<WaitlistConfirmation> {
    const confirmation = await registrationApi.joinWaitlist(eventId);
    await refresh();
    return confirmation;
  }

  async function acceptOffer(registrationId: string): Promise<RegistrationConfirmation> {
    const confirmation = await registrationApi.acceptOffer(registrationId);
    await refresh();
    return confirmation;
  }

  async function withdraw(registrationId: string): Promise<WithdrawalResult> {
    const result = await registrationApi.withdraw(registrationId);
    await refresh();
    return result;
  }

  return { events, myRegistrations, loading, error, refresh, register, joinWaitlist, acceptOffer, withdraw };
}
