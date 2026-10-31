import { ApiError, apiClient } from "../../api/client";
import { formatEventDate, formatEventTimeRange, formatInstantTime } from "../registration/datetime";
import type {
  BookingEvaluation,
  BookingFormValues,
  EventVenues,
  NextAction,
  PreparationStatus,
  BookingRejectWrite,
  TimeWindow,
  VenueBooking,
  VenueBookingCreated,
  VenueBookingStatus,
  VenueBookingsResponse,
  VenueBookingWrite,
} from "./bookingTypes";
import { tagLabel } from "./tags";
import type { Venue } from "./types";

// US22 booking routes identify the caller by X-User-Id: a coordinator requests and withdraws,
// Venue Staff read the pending list and, since US4 (SCRUM-8),
// approve or reject a request as a whole.
export const bookingApi = {
  create: (body: VenueBookingWrite) => apiClient.post<VenueBookingCreated>("/api/v1/venue-bookings", body),

  withdraw: (id: string) => apiClient.post<VenueBooking>(`/api/v1/venue-bookings/${id}/withdraw`, {}),

  // US24 (SCRUM-128): an event's venues, with whether they're arranged (D67, D72) and who acts next (D71).
  // The event's coordinator, Venue staff and, once approved, its Organiser may read it.
  eventVenues: (eventId: string) => apiClient.get<EventVenues>(`/api/v1/events/${eventId}/venue-bookings`),

  // US24 AC 4 (D68): the venue attendees see, once it's approved (D70).
  makePrimary: (id: string) => apiClient.post<VenueBooking>(`/api/v1/venue-bookings/${id}/make-primary`, {}),

  // US24 AC 7 (D73): Venue staff only, on an approved booking.
  setPreparation: (id: string, preparationStatus: PreparationStatus) =>
    apiClient.post<VenueBooking>(`/api/v1/venue-bookings/${id}/preparation`, { preparation_status: preparationStatus }),

  // Nothing to send: a request is approved as it stands (US4 AC 7).
  approve: (id: string) => apiClient.post<VenueBooking>(`/api/v1/venue-bookings/${id}/approve`, {}),

  reject: (id: string, body: BookingRejectWrite) =>
    apiClient.post<VenueBooking>(`/api/v1/venue-bookings/${id}/reject`, body),

  async pending(): Promise<VenueBooking[]> {
    return (await apiClient.get<VenueBookingsResponse>("/api/v1/venue-bookings/pending")).bookings;
  },

  // US13 AC 4 (D36): Venue Staff only. What stands in the way of a booking now, with each overlap.
  evaluation: (id: string) => apiClient.get<BookingEvaluation>(`/api/v1/venue-bookings/${id}/evaluation`),
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
  if (form.purpose.trim()) body.purpose = form.purpose.trim();
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

/** An event as the venue screens name it: its name, else its request reference (US22, US21 D58). */
export function eventName(event: { name: string | null; request_reference: string | null }): string {
  return event.name || event.request_reference || "Untitled event";
}

/** A booking's window in Singapore time, e.g. "Fri, Nov 20, 10:00 AM – 12:00 PM". */
export function formatBookingWindow(booking: Pick<VenueBooking, "starts_at" | "ends_at">): string {
  const timed = { startsAt: booking.starts_at, endsAt: booking.ends_at };
  return `${formatEventDate(timed)}, ${formatEventTimeRange(timed)}`;
}

/** Just the times of a window, e.g. "9:45 AM – 12:15 PM", for one on a day already shown. */
export function formatWindowTimes(window: TimeWindow): string {
  return formatEventTimeRange({ startsAt: window.starts_at, endsAt: window.ends_at });
}

/** A booking's occupied window (US13), e.g. "9:45 AM – 12:15 PM". */
export function formatOccupied(booking: Pick<VenueBooking, "occupied_starts_at" | "occupied_ends_at">): string {
  return formatWindowTimes({ starts_at: booking.occupied_starts_at, ends_at: booking.occupied_ends_at });
}

/** A venue's opening or closing time ("HH:MM:SS", Singapore wall-clock) as the screens show times. */
export function formatVenueTime(time: string): string {
  return formatInstantTime(`2026-01-01T${time.slice(0, 5)}:00${SINGAPORE_OFFSET}`);
}

const MINUTE = 60_000;

/**
 * US13 AC 2: the window the venue would be occupied for this form, setup before and turnaround
 * after, as the API will store it. Null until the date and both times are filled in and the end is
 * after the start; the API decides whether it fits (hours, overlaps).
 */
export function occupiedPreview(form: BookingFormValues, venue: Venue): TimeWindow | null {
  const startsAt = singaporeInstant(form.date, form.startTime);
  const endsAt = singaporeInstant(form.date, form.endTime);
  if (!startsAt || !endsAt) return null;
  const start = new Date(startsAt).getTime();
  const end = new Date(endsAt).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return null;
  return {
    starts_at: new Date(start - venue.setup_minutes * MINUTE).toISOString(),
    ends_at: new Date(end + venue.turnaround_minutes * MINUTE).toISOString(),
  };
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

const PREPARATION_LABELS: Record<PreparationStatus, string> = {
  not_started: "Not started",
  in_progress: "In progress",
  ready: "Ready",
};

export const PREPARATION_STATUSES = Object.keys(PREPARATION_LABELS) as PreparationStatus[];

/** US24 AC 7 (D73): a venue's preparation status in words. */
export function preparationLabel(status: PreparationStatus): string {
  return PREPARATION_LABELS[status] ?? status;
}

const NEXT_ACTION_LABELS: Record<NextAction, string> = {
  venue_staff_to_decide: "Waiting for Venue staff",
  coordinator_to_rebook: "Coordinator to rebook",
  none: "Nothing to do",
};

/** US24 AC 4 (D71): who acts next on a booking, in words. */
export function nextActionLabel(action: NextAction): string {
  return NEXT_ACTION_LABELS[action] ?? action;
}

/**
 * US24 AC 7 (D67, D72): what stands between an event and its venues being arranged, for the coordinator
 * (who acts on it) or the Organiser (who reads it). Empty once they're arranged.
 */
export function venuesMissing(venues: EventVenues, audience: "coordinator" | "organiser"): string[] {
  if (venues.venues_arranged) return [];
  const live = venues.bookings.filter((b) => b.status === "requested" || b.status === "approved");
  const missing: string[] = [];
  if (live.length === 0 && venues.allocated_attendees === 0) missing.push("No venue requested yet");
  const waiting = live.filter((b) => b.status === "requested").length;
  if (waiting > 0) missing.push(`${waiting} waiting for Venue staff`);
  const closed = live.filter((b) => b.unavailability?.kind === "venue_inactive").length;
  if (closed > 0) missing.push(`${closed} at a venue no longer available`);
  if (venues.next_action === "choose_primary") {
    missing.push(
      audience === "coordinator"
        ? "Choose a primary venue: attendees see none until you do"
        : "The coordinator to choose a primary venue",
    );
  }
  const short = (venues.expected_attendees ?? 0) - venues.allocated_attendees;
  if (venues.expected_attendees !== null && short > 0) missing.push(`${short} more attendees to allocate`);
  return missing;
}

/** "Allocated 35 of 40 expected, short by 5" (D67). */
export function allocationText(venues: EventVenues): string {
  const { allocated_attendees: allocated, expected_attendees: expected } = venues;
  if (expected === null) return `Allocated ${allocated}`;
  const short = expected - allocated;
  return `Allocated ${allocated} of ${expected} expected${short > 0 ? `, short by ${short}` : ""}`;
}

function isWindow(value: unknown): value is TimeWindow {
  const window = value as { starts_at?: unknown; ends_at?: unknown } | null | undefined;
  return !!window && typeof window.starts_at === "string" && typeof window.ends_at === "string";
}

function conflictWindow(error: ApiError): string | null {
  return isWindow(error.body.conflict) ? formatBookingWindow(error.body.conflict) : null;
}

/** US13 AC 4: where, with buffers, the clash overlaps the request, e.g. "12:00 PM – 12:15 PM". */
function conflictOverlap(error: ApiError): string | null {
  const conflict = error.body.conflict as { overlap?: unknown } | undefined;
  return conflict && isWindow(conflict.overlap) ? formatWindowTimes(conflict.overlap) : null;
}

function conflictIsBlock(error: ApiError): boolean {
  return (error.body.conflict as { kind?: unknown } | undefined)?.kind === "block";
}

/** VENUE_OUTSIDE_HOURS (US13 AC 5): "8:00 AM – 6:00 PM", or null if the body lacks the hours. */
function openingHours(error: ApiError): string | null {
  const { opens_at: opens, closes_at: closes } = error.body;
  return typeof opens === "string" && typeof closes === "string" ? `${formatVenueTime(opens)} – ${formatVenueTime(closes)}` : null;
}

/** Why the occupied window doesn't fit the venue's hours, lower-case so it can follow "Can't approve: ". */
function outsideHoursReason(error: ApiError): string {
  const occupied = isWindow(error.body.occupied) ? formatWindowTimes(error.body.occupied) : null;
  const hours = openingHours(error);
  return `with setup and turnaround the venue would be occupied ${occupied ?? "for longer"}, outside its opening hours${hours ? ` of ${hours}` : ""}`;
}

const FALLBACK_MESSAGE = "The request could not be completed. Check the backend connection and try again.";

/** Readable text for the booking routes' error codes (§3, deviations 24 to 28, 43). */
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
      const overlap = conflictOverlap(error);
      if (window && overlap) {
        // US13 AC 4: the overlap, but not the other booking's reference, which is for Venue staff (D35).
        const what = conflictIsBlock(error) ? "closed" : "already booked";
        return `This venue is ${what} on ${window}. With setup and turnaround, that overlaps your request ${overlap}. Choose another time or venue.`;
      }
      return window
        ? `This venue is already booked or unavailable on ${window}. Choose another time or venue.`
        : "This venue isn't available at that time. Choose another time or venue.";
    }
    case "VENUE_OUTSIDE_HOURS": {
      const reason = outsideHoursReason(error);
      return `${reason[0].toUpperCase()}${reason.slice(1)}. Choose times that fit.`;
    }
    case "EVENT_NOT_BOOKABLE":
      return `Venues can only be requested for approved events or events in planning${status ? `; this one is ${status}` : ""}.`;
    case "BOOKING_NOT_LIVE":
      // US24 (D69): withdraw refuses only a rejected or already withdrawn booking.
      return `This booking can't be withdrawn${status ? `: it's ${status} now` : ""}.`;
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

/** US24 (D68): why a venue can't be made the primary one. */
export function primaryErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === "BOOKING_NOT_LIVE") {
    const status = typeof error.body.status === "string" ? error.body.status : null;
    return `This venue can't be the primary one${status ? `: it's ${status} now` : ""}.`;
  }
  return bookingErrorMessage(error);
}

/** US24 (D73): why Venue staff can't record a venue's preparation status. */
export function preparationErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  switch (error.code) {
    case "BOOKING_NOT_APPROVED": {
      const status = typeof error.body.status === "string" ? error.body.status : null;
      return `Only an approved booking is prepared${status ? `; this one is ${status} now` : ""}.`;
    }
    case "INVALID_BOOKING":
      return "Choose Not started, In progress or Ready.";
    case "FORBIDDEN":
      return "Only Venue staff record a venue's preparation.";
    default:
      return bookingErrorMessage(error);
  }
}

/** US4: why Venue staff can't approve or reject a request, in their words. */
export function decisionErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  switch (error.code) {
    case "VENUE_UNAVAILABLE": {
      const window = conflictWindow(error);
      // AC 3: no override. The request stays pending until it's rejected or withdrawn.
      if (window && error.body.buffers === true) {
        return `Can't approve: too close to a booking or closure on ${window} to fit the venue's setup and turnaround. Reject the request instead.`;
      }
      return window
        ? `Can't approve: the venue is already booked or unavailable on ${window}. Reject the request instead.`
        : `Can't approve: ${typeof error.body.message === "string" ? error.body.message : "the venue isn't available then."} Reject the request instead.`;
    }
    case "VENUE_OUTSIDE_HOURS":
      // US13 AC 5 (D32): the hours may have changed since the request.
      return `Can't approve: ${outsideHoursReason(error)} now. Reject the request instead.`;
    case "BOOKING_EXPIRED":
      return "Can't approve: this request's start time has passed. Reject it instead.";
    case "VENUE_CAPACITY_EXCEEDED":
      return `Can't approve: expected attendance is more than the venue's capacity${typeof error.body.capacity === "number" ? ` of ${error.body.capacity}` : ""} now. Reject the request instead.`;
    case "EVENT_NOT_BOOKABLE":
      return `Can't approve: the event is ${typeof error.body.status === "string" ? error.body.status.replaceAll("_", " ") : "no longer bookable"} now. Reject the request instead.`;
    case "BOOKING_NOT_PENDING":
      return `This request was already decided or withdrawn${typeof error.body.status === "string" ? ` (it's ${error.body.status} now)` : ""}. Reload the list.`;
    case "SELF_DECISION_NOT_ALLOWED":
      // US16b D51: whoever requested a booking, or coordinates its event, doesn't decide it.
      return "Another Venue staff member must decide this request, because you made it or coordinate its event.";
    case "FORBIDDEN":
      return "Only Venue staff can approve or reject venue requests. Switch Acting as to Venue staff.";
    case "NOT_FOUND":
      return "This request no longer exists. Reload the list.";
    default:
      return bookingErrorMessage(error);
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
      const overlap = conflictOverlap(error);
      if (overlap) {
        const what = conflictIsBlock(error) ? "a venue closure" : "another booking";
        return { starts_at: `With setup and turnaround, overlaps ${what} ${overlap}.` };
      }
      return { starts_at: window ? `Clashes with ${window}.` : "This time isn't available." };
    }
    case "VENUE_OUTSIDE_HOURS": {
      // US13 AC 5: on whichever end runs past the hours (both if it crosses midnight).
      const { opens_at: opens, closes_at: closes } = error.body;
      const messages: Record<string, string> = {
        starts_at: `With setup, starts before the venue opens${typeof opens === "string" ? ` at ${formatVenueTime(opens)}` : ""}.`,
        ends_at: `With turnaround, ends after the venue closes${typeof closes === "string" ? ` at ${formatVenueTime(closes)}` : ""}.`,
      };
      return Object.fromEntries(error.fields.filter((field) => field in messages).map((field) => [field, messages[field]]));
    }
    default:
      return {};
  }
}
