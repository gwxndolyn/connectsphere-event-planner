export type EventCategory = "workshop" | "social" | "career" | "performance";
export type EventFormat = "in-person" | "online";

export interface CampusEvent {
  id: string;
  title: string;
  description: string;
  category: EventCategory;
  format: EventFormat;
  startsAt: string;
  endsAt: string;
  venue?: string;
  joinUrl?: string;
  capacity: number;
  seedRegisteredCount: number;
  seedWaitlistCount?: number;
  registrationOpen: boolean;
}

export interface EventAvailability extends CampusEvent {
  registeredCount: number;
}

export interface Attendee {
  name: string;
  email: string;
}

export type RegistrationStatus = "confirmed" | "waitlisted";

export interface Registration {
  id: string;
  eventId: string;
  attendee: Attendee;
  status: RegistrationStatus;
  confirmationCode?: string;
  registeredAt: string;
}

export type RegistrationResult =
  | { status: "registered"; confirmationCode: string }
  | { status: "waitlisted" }
  | { status: "duplicate" };
