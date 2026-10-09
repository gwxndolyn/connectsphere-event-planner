import { useCallback, useEffect, useState } from "react";
import { registrationApi } from "./api";
import type { EventAvailability, MyRegistrations, RegistrationConfirmation, WithdrawalResult } from "./types";

const NO_REGISTRATIONS: MyRegistrations = { confirmed: [], waitlisted: [], offered: [] };

function loadBoth() {
  return Promise.all([registrationApi.listAvailable(), registrationApi.listMine()]);
}

/**
 * The attendee's view of events and registrations, from the API (SCRUM-79): the events board
 * (SCRUM-25), register (SCRUM-26), My Events (SCRUM-30/31) and withdraw (SCRUM-34). Both lists
 * are re-read after every change, so seat counts and sections always match the server.
 *
 * SCRUM-52 (join waitlist) and SCRUM-76 (accept an offer) add their actions here the same way:
 * call `registrationApi`, then `refresh()`.
 */
export function useEventRegistry() {
  const [events, setEvents] = useState<EventAvailability[]>([]);
  const [myRegistrations, setMyRegistrations] = useState<MyRegistrations>(NO_REGISTRATIONS);
  const [loading, setLoading] = useState(true);
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
    let current = true;
    void applyLoad(() => current);
    return () => {
      current = false;
    };
  }, [applyLoad]);

  const refresh = useCallback(() => applyLoad(), [applyLoad]);

  async function register(eventId: string, answers: Record<string, string>): Promise<RegistrationConfirmation> {
    const confirmation = await registrationApi.register(eventId, answers);
    await refresh();
    return confirmation;
  }

  async function withdraw(registrationId: string): Promise<WithdrawalResult> {
    const result = await registrationApi.withdraw(registrationId);
    await refresh();
    return result;
  }

  return { events, myRegistrations, loading, error, refresh, register, withdraw };
}
