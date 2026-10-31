// Shapes from backend/app/venue/schemas.py (US22, SCRUM-89). Datetimes are ISO 8601 from the API.
export type VenueBookingStatus = "requested" | "approved" | "rejected" | "withdrawn";

export interface BookingEvent {
  id: string;
  name: string | null;
  request_reference: string | null;
  status: string;
}

export interface BookingVenue {
  id: string;
  name: string;
  location: string;
  capacity: number;
}

export interface VenueBooking {
  id: string;
  // US13 (SCRUM-16) D33: e.g. "VB-2026-000123".
  reference: string;
  event: BookingEvent;
  venue: BookingVenue;
  requested_by_user_id: string;
  starts_at: string;
  ends_at: string;
  // US13: [starts_at − setup, ends_at + turnaround), the time the venue is taken.
  occupied_starts_at: string;
  occupied_ends_at: string;
  expected_attendees: number;
  room_layout: string;
  required_facilities: string[];
  required_accessibility_features: string[];
  special_requirements: string | null;
  status: VenueBookingStatus;
  created_at: string;
  updated_at: string;
  withdrawn_at: string | null;
  // US4 (SCRUM-8): Venue Staff's decision, null while pending or once withdrawn.
  decided_at: string | null;
  decided_by_user_id: string | null;
  rejection_reason: string | null;
  alternative_suggestion: string | null;
  // US24 (SCRUM-128): what the venue is for (D66), whether attendees see it (D68), and how far Venue
  // staff are with getting it ready (D73). PR 3 shows them.
  purpose: string;
  is_primary: boolean;
  preparation_status: PreparationStatus;
}

// US24 AC 7 (D73): how far Venue staff are with getting an approved venue ready.
export type PreparationStatus = "not_started" | "in_progress" | "ready";

// US24 AC 4 (D71): who acts next on a booking.
export type NextAction = "venue_staff_to_decide" | "coordinator_to_rebook" | "none";

/** Why a venue needs replacing: Venue staff rejected it, or the venue has been deactivated. */
export interface BookingUnavailability {
  kind: "rejected" | "venue_inactive";
  reason: string | null;
  alternative_suggestion: string | null;
}

/** A booking as GET /events/{id}/venue-bookings gives it (US24, SCRUM-128). */
export interface EventVenueBooking extends VenueBooking {
  unavailability: BookingUnavailability | null;
  next_action: NextAction;
}

/** GET /api/v1/events/{event_id}/venue-bookings: an event's venues and whether they're arranged (D67, D72). */
export interface EventVenues {
  bookings: EventVenueBooking[];
  venues_arranged: boolean;
  primary_booking_id: string | null;
  allocated_attendees: number;
  expected_attendees: number | null;
  next_action: "choose_primary" | null;
}

/** US4 AC 5: both optional; left out when blank. */
export interface BookingRejectWrite {
  reason?: string;
  alternative_suggestion?: string;
}

/** Something the request needs that the venue lacks (AC 3); the booking is still made. */
export interface BookingWarning {
  field: string;
  item: string;
  message: string;
}

export interface VenueBookingCreated extends VenueBooking {
  warnings: BookingWarning[];
}

export interface VenueBookingsResponse {
  bookings: VenueBooking[];
}

export interface TimeWindow {
  starts_at: string;
  ends_at: string;
}

/** US13 AC 4: something occupying part of a booking's window, from the evaluation (D36). */
export interface BookingConflict extends TimeWindow {
  kind: "booking" | "block";
  // The clashing booking's reference; null for a block, which may have a note instead.
  reference: string | null;
  note: string | null;
  // The clashing booking's window with its buffers (a block's own window).
  occupied: TimeWindow;
  // Exactly where the two occupied windows overlap.
  overlap: TimeWindow;
}

/** US13 AC 5: the occupied window runs outside these hours ("HH:MM:SS"); `fields` names the end. */
export interface BookingHours {
  opens_at: string;
  closes_at: string;
  fields: string[];
}

/** GET /api/v1/venue-bookings/{id}/evaluation: what stands in the way of approving it now. */
export interface BookingEvaluation {
  booking_id: string;
  reference: string;
  occupied: TimeWindow;
  conflicts: BookingConflict[];
  outside_hours: BookingHours | null;
  clear: boolean;
}

// The request body. Blank fields are left out, so the API's MISSING_REQUIRED_FIELD names them.
export interface VenueBookingWrite {
  event_id: string;
  venue_id?: string;
  starts_at?: string;
  ends_at?: string;
  expected_attendees?: number;
  room_layout?: string;
  required_facilities: string[];
  required_accessibility_features: string[];
  special_requirements?: string;
  // US24 (SCRUM-128): required; blank is left out so MISSING_REQUIRED_FIELD names it (D66).
  purpose?: string;
}

// The form as typed. Date and times are Singapore wall-clock (D9).
export interface BookingFormValues {
  venueId: string;
  date: string; // YYYY-MM-DD
  startTime: string; // HH:MM
  endTime: string;
  attendees: string;
  roomLayout: string;
  facilities: string[];
  accessibility: string[];
  specialRequirements: string;
  // US24: what this venue is for, e.g. "Main hall" or "Breakout A".
  purpose: string;
}
