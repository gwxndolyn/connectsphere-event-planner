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
  event: BookingEvent;
  venue: BookingVenue;
  requested_by_user_id: string;
  starts_at: string;
  ends_at: string;
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
}
