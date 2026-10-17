import { ApiError, apiClient } from "../../api/client";
import type { Venue, VenueFilters, VenuesResponse, VenueWrite } from "./types";

// Venue routes identify the caller by X-User-Id (the Acting as switch). Writes need Venue Staff,
// which is operations_manager in the backend until US16b (D19).
export const venueApi = {
  async list(filters: VenueFilters, staff: boolean): Promise<Venue[]> {
    const params = new URLSearchParams();
    if (filters.q.trim()) params.set("q", filters.q.trim());
    if (/^\d+$/.test(filters.minCapacity.trim())) params.set("min_capacity", filters.minCapacity.trim());
    filters.facilities.forEach((tag) => params.append("facilities", tag));
    filters.accessibility.forEach((tag) => params.append("accessibility", tag));
    if (staff && filters.active !== "all") params.set("active", String(filters.active === "active"));
    const query = params.toString();
    const body = await apiClient.get<VenuesResponse>(`/api/v1/venues${query ? `?${query}` : ""}`);
    return body.venues;
  },

  create: (venue: VenueWrite) => apiClient.post<Venue>("/api/v1/venues", venue),

  update: (id: string, venue: VenueWrite) => apiClient.patch<Venue>(`/api/v1/venues/${id}`, venue),

  setActive: (id: string, active: boolean) =>
    apiClient.post<Venue>(`/api/v1/venues/${id}/${active ? "reactivate" : "deactivate"}`, {}),
};

const FALLBACK_MESSAGE = "The request could not be completed. Check the backend connection and try again.";

/** Readable text for the venue routes' error codes (§3). Field-level messages come from `errors`. */
export function venueErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  switch (error.code) {
    case "INVALID_VENUE":
      return "Review the fields marked below and try again.";
    case "MISSING_REQUIRED_FIELD":
      return "Complete the fields marked below.";
    case "VENUE_BUFFERS_LOCKED":
      return typeof error.body.message === "string" ? error.body.message : "Setup and turnaround can't change right now.";
    case "FORBIDDEN":
      return "Only Venue Staff can change venues.";
    case "NOT_FOUND":
      return "This venue is no longer available.";
    case "UNAUTHENTICATED":
      return "Set the dev user id for the role you're acting as in frontend/.env (VITE_DEV_VENUE_STAFF_ID for Venue staff), then restart the frontend.";
    default:
      return FALLBACK_MESSAGE;
  }
}

/** The `errors` map of an INVALID_VENUE response, plus "Required." for each MISSING_REQUIRED_FIELD. */
export function venueFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  if (error.code === "MISSING_REQUIRED_FIELD") {
    return Object.fromEntries(error.fields.map((field) => [field, "Required."]));
  }
  const errors = error.body.errors;
  if (error.code === "INVALID_VENUE" && errors && typeof errors === "object") {
    return Object.fromEntries(
      Object.entries(errors).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
    );
  }
  return {};
}
