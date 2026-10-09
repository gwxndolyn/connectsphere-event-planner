export type EventFormat = "in-person" | "online";

export interface RegistrationField {
  key: string;
  label: string;
  type: string;
  options: string[] | null;
  required: boolean;
}

/** One event from `GET /events/available`: open for registration right now (SCRUM-25). */
export interface EventAvailability {
  id: string;
  title: string;
  format: EventFormat;
  startsAt: string;
  endsAt: string;
  venue?: string;
  joinUrl?: string;
  capacity: number;
  seatsRemaining: number;
  isFull: boolean;
  alreadyRegistered: boolean;
  registrationFields: RegistrationField[];
}

/** The event as the register confirmation describes it (date, time and venue, per the AC). */
export interface ConfirmedEvent {
  title: string;
  startsAt: string;
  endsAt: string;
  venue?: string;
  joinUrl?: string;
}

export interface RegistrationConfirmation {
  registrationId: string;
  status: string;
  event: ConfirmedEvent;
}

export type MyRegistrationStatus = "confirmed" | "waitlisted" | "offered";

/** One row of `GET /me/registrations`, rendered as-is (§3). */
export interface MyRegistration {
  id: string;
  // Matches the row to its card on the events board.
  eventId: string;
  status: MyRegistrationStatus;
  eventTitle: string;
  date: string; // YYYY-MM-DD, Asia/Singapore
  startTime: string; // HH:MM
  endTime: string;
  format: EventFormat;
  venue?: string;
  // Room number in person, join link online (TC-US11-02, 03).
  joiningInfo: string;
  waitlistPosition?: number;
  // US6b: shown once SCRUM-76 builds "Accept place".
  offerExpiresAt?: string;
}

export interface MyRegistrations {
  confirmed: MyRegistration[];
  waitlisted: MyRegistration[];
  offered: MyRegistration[];
}

export interface WithdrawalResult {
  status: string;
  withdrawnAt: string;
  eventTitle: string;
  seatsRemaining: number;
}
