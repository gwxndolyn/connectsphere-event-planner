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
