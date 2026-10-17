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
