import type { TimeWindow, VenueBookingStatus } from "./bookingTypes";

// Shapes from backend/app/venue/schemas.py (US20, SCRUM-87). Times are "HH:MM:SS" from the API.
export interface Venue {
  id: string;
  name: string;
  location: string;
  capacity: number;
  facilities: string[];
  accessibility_features: string[];
  room_layouts: string[];
  opens_at: string;
  closes_at: string;
  setup_minutes: number;
  turnaround_minutes: number;
  is_active: boolean;
}

export interface VenuesResponse {
  venues: Venue[];
}

// Create and edit body. Every field is sent on save; resending an unchanged buffer isn't an edit.
export interface VenueWrite {
  name: string;
  location: string;
  capacity: number | null;
  facilities: string[];
  accessibility_features: string[];
  room_layouts: string[];
  opens_at: string | null;
  closes_at: string | null;
  setup_minutes: number | null;
  turnaround_minutes: number | null;
}

export type VenueField = keyof VenueWrite;

export type ActiveFilter = "active" | "inactive" | "all";

export interface VenueFilters {
  q: string;
  minCapacity: string;
  facilities: string[];
  accessibility: string[];
  // Staff only; everyone else always gets active venues.
  active: ActiveFilter;
}

// US2 venue search (SCRUM-7). Form values as typed; the API echoes what it applied.
export interface VenueSearchForm {
  date: string; // YYYY-MM-DD, Singapore
  startTime: string; // HH:MM
  endTime: string;
  attendees: string;
  location: string;
  facilities: string[];
  accessibility: string[];
}

export interface VenueSearchCriteria {
  date: string;
  start_time: string; // HH:MM:SS
  end_time: string;
  attendees: number;
  location: string | null;
  facilities: string[];
  accessibility: string[];
}

export interface VenueSearchResponse {
  venues: Venue[];
  criteria: VenueSearchCriteria;
}

// US21 (SCRUM-88): GET /api/v1/venues/{id}/calendar (VenueCalendarOut in backend/app/venue/schemas.py).
export interface CalendarVenue {
  id: string;
  name: string;
  is_active: boolean;
  opens_at: string;
  closes_at: string;
  setup_minutes: number;
  turnaround_minutes: number;
}

export interface CalendarEvent {
  // Null until the event is named; the request reference stands in (D58).
  name: string | null;
  request_reference: string | null;
  status: string;
}

export interface CalendarBooking {
  id: string;
  // Only for Venue staff, Leads and the event's coordinator; null for anyone else (D58).
  reference: string | null;
  status: VenueBookingStatus;
  event: CalendarEvent;
}

export interface CalendarItem {
  // "hold" is reserved until US25 (SCRUM-93) adds holds; none are returned yet (D59).
  kind: "booking" | "block" | "hold";
  label: string;
  starts_at: string;
  ends_at: string;
  // With setup and turnaround for a booking (US13); a block's own times.
  occupied: TimeWindow;
  booking: CalendarBooking | null;
  note: string | null;
}

export interface VenueCalendar {
  venue: CalendarVenue;
  // The Singapore days asked for, both included (D61).
  from: string;
  to: string;
  items: CalendarItem[];
}
