export type EventCategory = "workshop" | "social" | "career" | "performance";

export interface CampusEvent {
  id: string;
  title: string;
  description: string;
  category: EventCategory;
  date: string;
  time: string;
  venue: string;
  capacity: number;
  registeredCount: number;
  registrationOpen: boolean;
}

export interface Attendee {
  name: string;
  email: string;
}

export type RegistrationResult =
  | { status: "registered"; confirmationCode: string }
  | { status: "waitlisted" }
  | { status: "duplicate" };
