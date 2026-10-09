import { ApiError, apiClient } from "../../api/client";
import type {
  EventAvailability,
  EventFormat,
  MyRegistration,
  MyRegistrations,
  MyRegistrationStatus,
  RegistrationConfirmation,
  WithdrawalResult,
} from "./types";

// Response shapes from backend/app/event/schemas.py and backend/app/registration/schemas.py.
type DeliveryMode = "in_person" | "online";

interface RegistrationFieldOut {
  field_key: string;
  label: string;
  field_type: string;
  options: string[] | null;
  required: boolean;
}

interface AvailableEventOut {
  id: string;
  name: string;
  start_at: string;
  end_at: string;
  delivery_mode: DeliveryMode;
  venue_name: string | null;
  join_link: string | null;
  capacity: number;
  seats_remaining: number;
  is_full: boolean;
  already_registered: boolean;
  registration_fields: RegistrationFieldOut[];
}

interface RegisterResponseOut {
  registration_id: string;
  status: string;
  event: {
    name: string;
    start_at: string;
    end_at: string;
    venue_name: string | null;
    join_link: string | null;
  };
}

interface MyRegistrationOut {
  registration_id: string;
  event_id: string;
  event_name: string;
  date: string;
  start_time: string;
  end_time: string;
  venue_name: string | null;
  joining_info: string;
  delivery_mode: DeliveryMode;
  waitlist_position?: number;
  offer_expires_at?: string;
}

interface MyRegistrationsOut {
  confirmed: MyRegistrationOut[];
  waitlisted: MyRegistrationOut[];
  offered?: MyRegistrationOut[];
}

interface WithdrawResponseOut {
  status: string;
  withdrawn_at: string;
  event_name: string;
  seats_remaining: number;
}

function toFormat(mode: DeliveryMode): EventFormat {
  return mode === "online" ? "online" : "in-person";
}

function toEvent(event: AvailableEventOut): EventAvailability {
  return {
    id: event.id,
    title: event.name,
    format: toFormat(event.delivery_mode),
    startsAt: event.start_at,
    endsAt: event.end_at,
    venue: event.venue_name ?? undefined,
    joinUrl: event.join_link ?? undefined,
    capacity: event.capacity,
    seatsRemaining: event.seats_remaining,
    isFull: event.is_full,
    alreadyRegistered: event.already_registered,
    registrationFields: event.registration_fields.map((field) => ({
      key: field.field_key,
      label: field.label,
      type: field.field_type,
      options: field.options,
      required: field.required,
    })),
  };
}

function toMyRegistration(row: MyRegistrationOut, status: MyRegistrationStatus): MyRegistration {
  return {
    id: row.registration_id,
    eventId: row.event_id,
    status,
    eventTitle: row.event_name,
    date: row.date,
    startTime: row.start_time,
    endTime: row.end_time,
    format: toFormat(row.delivery_mode),
    venue: row.venue_name ?? undefined,
    joiningInfo: row.joining_info,
    waitlistPosition: row.waitlist_position,
    offerExpiresAt: row.offer_expires_at,
  };
}

// Every call here is an attendee route, identified by X-Attendee-Id. SCRUM-52 (join waitlist,
// email-only per D7) and SCRUM-76 (accept an offer) add their calls alongside these.
export const registrationApi = {
  async listAvailable(): Promise<EventAvailability[]> {
    const body = await apiClient.get<{ events: AvailableEventOut[] }>("/api/v1/events/available", "attendee");
    return body.events.map(toEvent);
  },

  async listMine(): Promise<MyRegistrations> {
    const body = await apiClient.get<MyRegistrationsOut>("/api/v1/me/registrations", "attendee");
    return {
      confirmed: body.confirmed.map((row) => toMyRegistration(row, "confirmed")),
      waitlisted: body.waitlisted.map((row) => toMyRegistration(row, "waitlisted")),
      offered: (body.offered ?? []).map((row) => toMyRegistration(row, "offered")),
    };
  },

  async register(eventId: string, answers: Record<string, string>): Promise<RegistrationConfirmation> {
    const body = await apiClient.post<RegisterResponseOut>(
      `/api/v1/events/${eventId}/registrations`,
      { answers },
      "attendee",
    );
    return {
      registrationId: body.registration_id,
      status: body.status,
      event: {
        title: body.event.name,
        startsAt: body.event.start_at,
        endsAt: body.event.end_at,
        venue: body.event.venue_name ?? undefined,
        joinUrl: body.event.join_link ?? undefined,
      },
    };
  },

  async withdraw(registrationId: string): Promise<WithdrawalResult> {
    const body = await apiClient.post<WithdrawResponseOut>(
      `/api/v1/registrations/${registrationId}/withdraw`,
      {},
      "attendee",
    );
    return {
      status: body.status,
      withdrawnAt: body.withdrawn_at,
      eventTitle: body.event_name,
      seatsRemaining: body.seats_remaining,
    };
  },
};

/** A short, quotable reference for the confirmation ticket. The API has no confirmation code. */
export function bookingReference(registrationId: string): string {
  return registrationId.replace(/-/g, "").slice(0, 8).toUpperCase();
}

const FALLBACK_MESSAGE = "The request could not be completed. Check the backend connection and try again.";

/** Readable text for the attendee routes' error codes (§3). `fieldLabels` names MISSING_REQUIRED_FIELD's keys. */
export function registrationErrorMessage(error: unknown, fieldLabels: Record<string, string> = {}): string {
  if (!(error instanceof ApiError)) return FALLBACK_MESSAGE;
  switch (error.code) {
    case "EVENT_FULL":
      return "This event filled up before your registration went through.";
    case "ALREADY_REGISTERED":
      return "You're already registered for this event.";
    case "REGISTRATION_CLOSED":
      return "Registration for this event isn't open right now.";
    case "REGISTRATION_NOT_ENABLED":
      return "This event isn't taking registrations.";
    case "MISSING_REQUIRED_FIELD":
      return `Please answer: ${error.fields.map((key) => fieldLabels[key] ?? key).join(", ")}.`;
    case "NOT_FOUND":
      return "We couldn't find that event or registration. It may have been removed.";
    case "EVENT_STARTED":
      return "This event has already started, so you can't withdraw.";
    case "ALREADY_WITHDRAWN":
    case "REGISTRATION_NOT_ACTIVE":
      return "This registration is no longer active.";
    case "UNAUTHENTICATED":
      return "Set VITE_DEV_ATTENDEE_ID in frontend/.env to the seeded attendee ID, then restart the frontend.";
    default:
      return FALLBACK_MESSAGE;
  }
}
