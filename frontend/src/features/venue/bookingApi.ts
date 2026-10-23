import { ApiError, apiClient } from "../../api/client";
import { formatEventDate, formatEventTimeRange } from "../registration/datetime";
import type {
  BookingFormValues,
  VenueBooking,
  VenueBookingCreated,
  VenueBookingStatus,
  VenueBookingsResponse,
  VenueBookingWrite,
} from "./bookingTypes";
import { tagLabel } from "./tags";
import type { Venue } from "./types";

// US22 booking routes identify the caller by X-User-Id: a coordinator requests and withdraws,
// Venue Staff (operations_manager until US16b, D19) read the pending list.
export const bookingApi = {
  create: (body: VenueBookingWrite) => apiClient.post<VenueBookingCreated>("/api/v1/venue-bookings", body),

  withdraw: (id: string) => apiClient.post<VenueBooking>(`/api/v1/venue-bookings/${id}/withdraw`, {}),

  async forEvent(eventId: string): Promise<VenueBooking[]> {
    return (await apiClient.get<VenueBookingsResponse>(`/api/v1/events/${eventId}/venue-bookings`)).bookings;
  },

  async pending(): Promise<VenueBooking[]> {
    return (await apiClient.get<VenueBookingsResponse>("/api/v1/venue-bookings/pending")).bookings;
  },
};

// Every event is in Singapore (D9), so the window is sent with its +08:00 offset; the API refuses a
// time without one (INVALID_BOOKING).
const SINGAPORE_OFFSET = "+08:00";

function singaporeInstant(date: string, time: string): string | undefined {
  return date && time ? `${date}T${time}:00${SINGAPORE_OFFSET}` : undefined;
}

/** The request body. Blank fields are left out, so MISSING_REQUIRED_FIELD names each one. */
export function toBookingBody(eventId: string, form: BookingFormValues): VenueBookingWrite {
  const body: VenueBookingWrite = {
    event_id: eventId,
    required_facilities: form.facilities,
    required_accessibility_features: form.accessibility,
  };
  const startsAt = singaporeInstant(form.date, form.startTime);
  const endsAt = singaporeInstant(form.date, form.endTime);
  if (form.venueId) body.venue_id = form.venueId;
  if (startsAt) body.starts_at = startsAt;
  if (endsAt) body.ends_at = endsAt;
  if (/^\d+$/.test(form.attendees.trim())) body.expected_attendees = Number(form.attendees.trim());
  if (form.roomLayout) body.room_layout = form.roomLayout;
  if (form.specialRequirements.trim()) body.special_requirements = form.specialRequirements.trim();
  return body;
}

/** What the request asks for that the venue doesn't list (AC 3: warned, but can still submit). */
export function missingForVenue(form: BookingFormValues, venue: Venue): string[] {
  return [
    ...form.facilities.filter((tag) => !venue.facilities.includes(tag)).map(tagLabel),
    ...form.accessibility.filter((tag) => !venue.accessibility_features.includes(tag)).map(tagLabel),
    ...(form.roomLayout && !venue.room_layouts.includes(form.roomLayout) ? [`${tagLabel(form.roomLayout)} layout`] : []),
  ];
}

/** A booking's window in Singapore time, e.g. "Fri, Nov 20, 10:00 AM – 12:00 PM". */
export function formatBookingWindow(booking: Pick<VenueBooking, "starts_at" | "ends_at">): string {
  const timed = { startsAt: booking.starts_at, endsAt: booking.ends_at };
  return `${formatEventDate(timed)}, ${formatEventTimeRange(timed)}`;
}

const STATUS_LABELS: Record<VenueBookingStatus, string> = {
  requested: "Requested",
  approved: "Approved",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export function bookingStatusLabel(status: VenueBookingStatus): string {
  return STATUS_LABELS[status] ?? status;
}

function conflictWindow(error: ApiError): string | null {
  const conflict = error.body.conflict as { starts_at?: unknown; ends_at?: unknown } | undefined;
  if (!conflict || typeof conflict.starts_at !== "string" || typeof conflict.ends_at !== "string") return null;
  return formatBookingWindow({ starts_at: conflict.starts_at, ends_at: conflict.ends_at });
}

const FALLBACK_MESSAGE = "The request could not be completed. Check the backend connection and try again.";

/** Readable text for the booking routes' error codes (§3, deviations 24 to 28). */
export function bookingErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  const status = typeof error.body.status === "string" ? error.body.status.replaceAll("_", " ") : null;
  switch (error.code) {
    case "MISSING_REQUIRED_FIELD":
      return "Complete the fields marked below.";
    case "INVALID_BOOKING":
      return "Review the fields marked below and try again.";
    case "VENUE_CAPACITY_EXCEEDED":
      return typeof error.body.message === "string" ? error.body.message : "Expected attendance is more than this venue's capacity.";
    case "VENUE_UNAVAILABLE": {
      const window = conflictWindow(error);
      return window
        ? `This venue is already booked or unavailable on ${window}. Choose another time or venue.`
        : "This venue isn't available at that time. Choose another time or venue.";
    }
    case "EVENT_NOT_BOOKABLE":
      return `Venues can only be requested for approved events or events in planning${status ? `; this one is ${status}` : ""}.`;
    case "BOOKING_NOT_PENDING":
      return `This booking is no longer pending${status ? ` (it's ${status} now)` : ""}, so it can't be withdrawn.`;
    case "NOT_FOUND":
      return "This event, venue or booking is no longer available. Reload and try again.";
    case "FORBIDDEN":
      return "Only coordinators can request or withdraw venue bookings. Switch Acting as to Coordinator.";
    case "UNAUTHENTICATED":
      return "Set the dev user id for the role you're acting as in frontend/.env, then restart the frontend.";
    default:
      return FALLBACK_MESSAGE;
  }
}

/** A message per API field name, for the form to show beside its input. */
export function bookingFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError)) return {};
  switch (error.code) {
    case "MISSING_REQUIRED_FIELD":
      return Object.fromEntries(error.fields.map((field) => [field, "Required."]));
    case "INVALID_BOOKING": {
      const errors = error.body.errors;
      if (!errors || typeof errors !== "object") return {};
      return Object.fromEntries(
        Object.entries(errors).filter((entry): entry is [string, string] => typeof entry[1] === "string"),
      );
    }
    case "VENUE_CAPACITY_EXCEEDED":
      return { expected_attendees: bookingErrorMessage(error) };
    case "VENUE_UNAVAILABLE": {
      const window = conflictWindow(error);
      return { starts_at: window ? `Clashes with ${window}.` : "This time isn't available." };
    }
    default:
      return {};
  }
}
