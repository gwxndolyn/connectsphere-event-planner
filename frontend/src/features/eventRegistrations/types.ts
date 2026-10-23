// Shapes from backend/app/registration/schemas.py (US28, SCRUM-96). Instants are ISO strings.
export type RegistrationStatus = "confirmed" | "waitlisted" | "offered" | "withdrawn" | "declined" | "expired";

export interface ManagedEvent {
  id: string;
  name: string;
  start_at: string;
  end_at: string;
  status: string;
  capacity: number;
}

export interface ManagedEventsResponse {
  events: ManagedEvent[];
}

export interface RegistrationTotals {
  confirmed: number;
  waitlisted: number;
  offered: number;
  seats_remaining: number;
}

export interface RegistrationQuestion {
  field_key: string;
  label: string;
  field_type: string;
  options: string[] | null;
  required: boolean;
}

export interface EventRegistrant {
  registration_id: string;
  attendee_name: string | null;
  attendee_email: string;
  status: RegistrationStatus;
  registered_at: string;
  waitlist_position: number | null;
  offer_expires_at: string | null;
  answers: Record<string, string | null>;
}

export interface EventRegistrations {
  event: ManagedEvent;
  totals: RegistrationTotals;
  registration_fields: RegistrationQuestion[];
  registrations: EventRegistrant[];
}

/** "all": every active registration, or every registration with Show all (AC 4, 5). */
export interface RegistrationFilter {
  status: RegistrationStatus | "all";
  showAll: boolean;
}
