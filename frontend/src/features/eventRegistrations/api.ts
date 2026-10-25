import { ApiError, apiClient } from "../../api/client";
import type { EventRegistrations, ManagedEvent, ManagedEventsResponse, RegistrationFilter } from "./types";

// Staff routes, so X-User-Id (the Acting as switch). Organisers see their own events; coordinators
// only the events assigned to them (D52).
export const eventRegistrationsApi = {
  async listManagedEvents(): Promise<ManagedEvent[]> {
    const body = await apiClient.get<ManagedEventsResponse>("/api/v1/me/managed-events");
    return body.events;
  },

  // Which rows to show is the API's rule: a status filter wins, else Show all, else active rows only.
  list(eventId: string, filter: RegistrationFilter): Promise<EventRegistrations> {
    const params = new URLSearchParams();
    if (filter.status !== "all") params.set("status", filter.status);
    else if (filter.showAll) params.set("show_all", "true");
    const query = params.toString();
    return apiClient.get<EventRegistrations>(`/api/v1/events/${eventId}/registrations${query ? `?${query}` : ""}`);
  },
};

const FALLBACK_MESSAGE = "The request could not be completed. Check the backend connection and try again.";

/** Readable text for the registrations routes' error codes (§3). */
export function registrationsErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  switch (error.code) {
    case "FORBIDDEN":
      return "Only organisers and coordinators can view registrations. Switch Acting as to Organiser or Coordinator.";
    case "NOT_FOUND":
      return "This event isn't one you manage, or it no longer exists.";
    case "UNAUTHENTICATED":
      return "Set the dev user id for the role you're acting as in frontend/.env, then restart the frontend.";
    default:
      return FALLBACK_MESSAGE;
  }
}
