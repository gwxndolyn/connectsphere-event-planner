import { http, HttpResponse, type JsonBodyType } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll } from "vitest";
import type { EventRegistrations } from "../features/eventRegistrations/types";
import type { AuditEntry, EventDetails } from "../features/eventEdit/types";
import type { Cancellation } from "../features/cancellation/types";
import type { ChangeRequestReview, OrganiserChangeRequest, ReviewFlag } from "../features/changeRequest/types";
import type { AssignmentRecord, Clarification, EventRequest, EventRequestWrite } from "../features/eventRequest/types";
import type { BookingEvaluation, VenueBooking } from "../features/venue/bookingTypes";
import type { Venue } from "../features/venue/types";

/**
 * An in-memory stand-in for the FastAPI backend, for integration tests: the real apiClient,
 * hooks and screens run against it, so a flow (register, then My events, then withdraw) sees its
 * own writes. It follows §3's contracts and error codes, and checks the identity headers the same
 * way, so a screen sending the wrong header fails here as it would against the real API.
 */

const API = "http://api.test";
// The fixed ids vite.config.ts gives the tests (VITE_DEV_*).
export const ORGANISER_ID = "organiser-id";
export const COORDINATOR_ID = "coordinator-id";
export const LEAD_ID = "lead-id";
export const VENUE_STAFF_ID = "venue-staff-id";
export const TECH_SUPPORT_ID = "tech-support-id";
export const SAFETY_OFFICER_ID = "safety-officer-id";
export const ATTENDEE_ID = "attendee-id";
export const ATTENDEE_EMAIL = "calvin.ng.2024@smu.edu.sg";

export interface FakeEvent {
  id: string;
  name: string;
  // Always +08:00, so My events' date and times can be sliced from it.
  start_at: string;
  end_at: string;
  delivery_mode: "in_person" | "online";
  venue_name: string | null;
  room_number: string | null;
  join_link: string | null;
  capacity: number;
  waitlist_enabled: boolean;
  registration_fields: { field_key: string; label: string; field_type: string; options: string[] | null; required: boolean }[];
}

export interface FakeRegistration {
  id: string;
  event_id: string;
  attendee_id: string | null;
  email: string;
  // "expired": an offer that lapsed (SCRUM-137), seeded by a test; the fake backend doesn't sweep.
  status: "confirmed" | "waitlisted" | "offered" | "expired";
  // Queue order: position is derived from it, never stored (§2).
  joined: number;
  offer_expires_at?: string;
  answers?: Record<string, string>;
}

// US26 equipment (SCRUM-109's API, SCRUM-110's screens). Kept here rather than imported from the
// feature, so the fake backend's contract is written down once, from §3.
export interface FakeEquipmentType {
  id: string;
  name: string;
}

export interface FakeEquipmentEvent {
  id: string;
  name: string;
  start_at: string;
  status: string;
  // The assigned coordinator (D20): only they list, add, edit and remove its lines.
  coordinator_id: string | null;
}

export interface FakeEquipmentLine {
  id: string;
  event: { id: string; name: string | null; start_at: string | null };
  equipment_type: FakeEquipmentType;
  quantity: number;
  notes: string | null;
  status: "pending" | "approved" | "rejected";
  review_note: string | null;
  requested_by_user_id: string;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  // US5 (SCRUM-125, D64): the latest availability check, or null.
  availability_check: FakeAvailabilityCheck | null;
  // US27 (SCRUM-131): the line's reservation, or null.
  reservation: FakeReservation | null;
  created_at: string;
  updated_at: string;
}

export interface FakeReservation {
  quantity: number;
  reserved_by_user_id: string;
  reserved_at: string;
  // D75: a cancelled event's reservation counts as released until US9 deletes it.
  released_because_event_cancelled: boolean;
}

/** Why POST /equipment-lines/{id}/reservation refuses a line short of stock (SCRUM-131). */
export interface FakeReservationShortfall {
  available: number;
  requested: number;
  shortfall: number;
}

export interface FakeAvailabilityCheck {
  sufficient: boolean;
  shortfall: number;
  checked_by_user_id: string;
  checked_at: string;
}

/** What POST /equipment-lines/{id}/availability-check answers (SCRUM-125), less who and when. */
export interface FakeAvailability {
  line_id: string;
  equipment_type: { id: string; name: string; storage_location: string | null };
  window: { starts_at: string; ends_at: string };
  requested: number;
  total: number;
  out_of_service: number;
  reserved_elsewhere: number;
  available: number;
  sufficient: boolean;
  shortfall: number;
}

// US14 Tech support staff (SCRUM-134's API, SCRUM-135's screen): a staff member, or who acted.
export interface FakePerson {
  id: string;
  name: string;
}

// US15 (SCRUM-139's API, SCRUM-140's screen): one agenda session, as GET .../sessions returns it.
export interface FakeSession {
  id: string;
  event_id: string;
  title: string;
  session_type: "presentation" | "workshop" | "panel" | "break" | "other";
  speaker_name: string | null;
  starts_at: string;
  ends_at: string;
  outside_window: boolean;
}

/** One assignment, active until unassigned; the rows are also the log (D79). */
interface FakeTechStaffRow {
  event_id: string;
  staff: FakePerson;
  assigned_by: FakePerson;
  assigned_at: string;
  unassigned_by: FakePerson | null;
  unassigned_at: string | null;
}

// US2's venue closures, which the US21 calendar shows as "Unavailable" (SCRUM-123).
export interface FakeVenueBlock {
  id: string;
  venue_id: string;
  starts_at: string;
  ends_at: string;
  note: string | null;
  // US23a (SCRUM-90): why the venue is out of use.
  reason: string;
  // The bookings and holds it marked as needing rearrangement (D113), by id.
  affects: string[];
  // US23b (SCRUM-91, D118): Venue staff ended it early (ends_at is then); the end it had.
  ended_early_at?: string | null;
  scheduled_ends_at?: string | null;
}

export interface RecordedCall {
  method: string;
  path: string;
  url: URL;
  headers: Headers;
  body: unknown;
}

// US30a (SCRUM-99): a stored safety review, as the Safety Officer's routes return it.
export interface FakeSafetyReview {
  id: string;
  event_id: string;
  outcome: "approved" | "rejected" | "changes_requested";
  checklist: Record<string, { result: "satisfactory" | "issue"; comment: string | null }>;
  comments: string | null;
  internal_notes: string | null;
  // US30b: the areas a request for changes marked; null for any other outcome.
  areas: string[] | null;
  reviewer: { id: string; name: string };
  created_at: string;
}

// US29b (SCRUM-143): a change request as the fake keeps it: the organiser's view, plus who asked and decided.
export type FakeChangeRequest = OrganiserChangeRequest & {
  // The event's organiser when not given (US29a's requests).
  requested_by_user_id?: string;
  decided_by?: { id: string; name: string } | null;
};

// US31 (SCRUM-107): a stored notification, as GET /api/v1/me/notifications returns it, with its recipient.
export interface FakeNotification {
  id: string;
  user_id: string;
  kind: string;
  event_id: string | null;
  event_name: string | null;
  message: string;
  created_at: string;
  read: boolean;
  can_open: boolean;
}

interface Db {
  venues: Venue[];
  // What GET /venues/available returns next (see nextSearchResult).
  searchResult: Venue[];
  events: FakeEvent[];
  registrations: FakeRegistration[];
  requests: EventRequest[];
  // SCRUM-69: each request's Assignment History, newest first.
  assignments: Record<string, AssignmentRecord[]>;
  // Who GET /coordinators offers beyond Casey (SCRUM-83 needs a second one to move an event to).
  otherCoordinators: { id: string; name: string; email: string }[];
  clarifications: Clarification[];
  // US22 venue bookings (SCRUM-113).
  bookings: VenueBooking[];
  // US2 venue closures, for the US21 calendar (SCRUM-123).
  blocks: FakeVenueBlock[];
  // US13 (SCRUM-116): what GET /venue-bookings/{id}/evaluation finds, by booking id (see setEvaluation).
  evaluations: Record<string, Pick<BookingEvaluation, "conflicts" | "outside_hours">>;
  // US26 equipment (SCRUM-110).
  equipmentTypes: FakeEquipmentType[];
  equipmentEvents: FakeEquipmentEvent[];
  equipmentLines: FakeEquipmentLine[];
  // US5 (SCRUM-126): what each line's availability check finds, by line id (see setAvailability).
  availability: Record<string, FakeAvailability>;
  // US27 (SCRUM-132): lines whose reservation the API refuses for want of stock (see refuseReservation).
  reservationShortfalls: Record<string, FakeReservationShortfall>;
  // US14 (SCRUM-135): the active Tech support users, and every assignment.
  techStaff: FakePerson[];
  techStaffRows: FakeTechStaffRow[];
  // US30a: every safety review, and the events whose rejected arrangement was sent back for another one.
  safetyReviews: FakeSafetyReview[];
  safetyResent: Record<string, boolean>;
  // US31: every user's notifications; the routes show the caller's own.
  notifications: FakeNotification[];
  // US28: the events each managing role sees, and what each event's registrations call returns.
  managedEvents: Record<"organiser" | "coordinator", EventRegistrations[]>;
  // US12 (SCRUM-15): the coordinator's events and each one's History, newest first.
  coordinatedEvents: EventDetails[];
  history: Record<string, AuditEntry[]>;
  // US29a (SCRUM-97): organisers' change requests, newest first. US29b (SCRUM-143): who asked, and who decided.
  changeRequests: FakeChangeRequest[];
  // US29b (SCRUM-143): the review flags an approved significant change raised.
  reviewFlags: ReviewFlag[];
  // Roles a user holds besides ROLES' one (US16b), e.g. a coordinator who is also a Lead, like multi.role.
  extraRoles: Record<string, string[]>;
  // US9 (SCRUM-12): cancellation requests and cancels, newest first.
  cancellations: Cancellation[];
  // US15 (SCRUM-140): every event's agenda sessions.
  sessions: FakeSession[];
  calls: RecordedCall[];
  nextId: number;
  nextReference: number;
  nextBookingReference: number;
}

function emptyDb(): Db {
  return {
    venues: [],
    searchResult: [],
    events: [],
    registrations: [],
    requests: [],
    assignments: {},
    otherCoordinators: [],
    clarifications: [],
    managedEvents: { organiser: [], coordinator: [] },
    coordinatedEvents: [],
    history: {},
    changeRequests: [],
    reviewFlags: [],
    extraRoles: {},
    cancellations: [],
    sessions: [],
    bookings: [],
    blocks: [],
    evaluations: {},
    equipmentTypes: [],
    equipmentEvents: [],
    equipmentLines: [],
    availability: {},
    reservationShortfalls: {},
    techStaff: [],
    techStaffRows: [],
    safetyReviews: [],
    safetyResent: {},
    notifications: [],
    calls: [],
    nextId: 1,
    nextReference: 1,
    nextBookingReference: 1,
  };
}

export let db: Db = emptyDb();

function newId(kind: string): string {
  return `${kind}-${db.nextId++}`;
}

// --- Seeding helpers --------------------------------------------------------------------------

export function seedEvent(overrides: Partial<FakeEvent> = {}): FakeEvent {
  const event: FakeEvent = {
    id: newId("event"),
    name: "Tech Talk: Agile at Scale",
    start_at: "2026-10-02T14:00:00+08:00",
    end_at: "2026-10-02T16:00:00+08:00",
    delivery_mode: "in_person",
    venue_name: "SMU SCIS Building",
    room_number: "Seminar Room 2-1",
    join_link: null,
    capacity: 40,
    waitlist_enabled: false,
    registration_fields: [],
    ...overrides,
  };
  db.events.push(event);
  return event;
}

/** A registration for the test's attendee unless `attendee_id`/`email` say otherwise. */
export function seedRegistration(
  event: FakeEvent,
  overrides: Partial<FakeRegistration> = {},
): FakeRegistration {
  const registration: FakeRegistration = {
    id: newId("registration"),
    event_id: event.id,
    attendee_id: ATTENDEE_ID,
    email: ATTENDEE_EMAIL,
    status: "confirmed",
    joined: db.nextId,
    ...overrides,
  };
  db.registrations.push(registration);
  return registration;
}

/** Someone else's confirmed seat, to fill an event. */
export function fillSeats(event: FakeEvent, count: number) {
  for (let i = 0; i < count; i++) {
    seedRegistration(event, { attendee_id: `other-${db.nextId}`, email: `other${db.nextId}@smu.edu.sg` });
  }
}

/** US31: a notification for `userId`, unread unless `read` says otherwise. */
export function seedNotification(userId: string, overrides: Partial<FakeNotification> = {}): FakeNotification {
  const notification: FakeNotification = {
    id: newId("notification"),
    user_id: userId,
    kind: "request_decided",
    event_id: null,
    event_name: "Alumni night",
    message: "Your request ER-2026-000101 was approved.",
    created_at: `2026-10-04T03:${String(db.notifications.length).padStart(2, "0")}:00Z`,
    read: false,
    can_open: false,
    ...overrides,
  };
  db.notifications.push(notification);
  return notification;
}

export function seedRequest(overrides: Partial<EventRequest> = {}): EventRequest {
  const request: EventRequest = {
    id: newId("request"),
    status: "draft",
    name: "Planning workshop",
    event_category: "Workshop",
    purpose: "Plan the next event",
    preferred_dates: ["2026-11-20"],
    preferred_start_time: "14:00:00",
    preferred_end_time: "16:00:00",
    expected_attendees: 40,
    room_layout_preference: null,
    accessibility_needs: null,
    equipment_needs: null,
    registration_required: null,
    created_by_user_id: ORGANISER_ID,
    submitted_by_user_id: null,
    submitted_at: null,
    request_reference: null,
    created_at: "2026-10-01T02:00:00Z",
    coordinator: null,
    decided_at: null,
    decided_by: null,
    rejection_reason: null,
    safety_approved_at: null,
    confirmed_at: null,
    ...overrides,
  };
  if (request.status !== "draft" && !request.request_reference) {
    request.request_reference = nextReference();
    request.submitted_by_user_id = request.created_by_user_id;
    request.submitted_at = request.created_at;
  }
  db.requests.push(request);
  return request;
}

export function seedClarification(request: EventRequest, overrides: Partial<Clarification> = {}): Clarification {
  const message: Clarification = {
    id: newId("clarification"),
    event_id: request.id,
    round: 1,
    kind: "request",
    sections: overrides.kind === "response" ? null : ["attendance"],
    comment: "Is 40 the final headcount?",
    author_user_id: overrides.kind === "response" ? ORGANISER_ID : COORDINATOR_ID,
    created_at: "2026-10-02T02:00:00Z",
    ...overrides,
  };
  db.clarifications.push(message);
  return message;
}

export function seedVenue(overrides: Partial<Venue> = {}): Venue {
  const venue: Venue = {
    id: newId("venue"),
    name: "SCIS Seminar Room 2-1",
    location: "School of Computing and Information Systems, Level 2",
    capacity: 40,
    facilities: ["projector", "wifi"],
    accessibility_features: ["wheelchair", "lift"],
    room_layouts: ["classroom"],
    opens_at: "08:00:00",
    closes_at: "22:00:00",
    setup_minutes: 15,
    turnaround_minutes: 15,
    is_active: true,
    ...overrides,
  };
  db.venues.push(venue);
  return venue;
}

const MINUTE = 60_000;

function shifted(iso: string, minutes: number): string {
  return new Date(new Date(iso).getTime() + minutes * MINUTE).toISOString().replace(".000Z", "Z");
}

/**
 * A US22 booking of `venue` for an event request (an approved one, in the screens' flows). US13: it
 * gets a VB- reference and the occupied window the venue's buffers make, unless overridden.
 */
export function seedBooking(request: EventRequest, venue: Venue, overrides: Partial<VenueBooking> = {}): VenueBooking {
  const starts_at = overrides.starts_at ?? "2026-11-20T02:00:00Z";
  const ends_at = overrides.ends_at ?? "2026-11-20T04:00:00Z";
  const booking: VenueBooking = {
    id: newId("booking"),
    reference: `VB-2026-${String(db.nextBookingReference++).padStart(6, "0")}`,
    event: { id: request.id, name: request.name, request_reference: request.request_reference, status: request.status },
    venue: { id: venue.id, name: venue.name, location: venue.location, capacity: venue.capacity },
    requested_by_user_id: COORDINATOR_ID,
    // Singapore 10:00–12:00 on 20 Nov 2026 by default.
    starts_at,
    ends_at,
    occupied_starts_at: shifted(starts_at, -venue.setup_minutes),
    occupied_ends_at: shifted(ends_at, venue.turnaround_minutes),
    expected_attendees: 30,
    room_layout: "classroom",
    required_facilities: [],
    required_accessibility_features: [],
    special_requirements: null,
    status: "requested",
    created_at: "2026-10-01T02:00:00Z",
    updated_at: "2026-10-01T02:00:00Z",
    withdrawn_at: null,
    decided_at: null,
    decided_by_user_id: null,
    rejection_reason: null,
    alternative_suggestion: null,
    purpose: "Main venue",
    is_primary: true,
    preparation_status: "not_started",
    hold_expires_at: null,
    held_by_user_id: null,
    expired_at: null,
    ...overrides,
  };
  db.bookings.push(booking);
  return booking;
}

/** A US2 closure of `venue`, Singapore 13:00–15:00 on 20 Nov 2026 unless overridden. */
export function seedBlock(venue: Venue, overrides: Partial<FakeVenueBlock> = {}): FakeVenueBlock {
  const block: FakeVenueBlock = {
    id: newId("block"),
    venue_id: venue.id,
    starts_at: "2026-11-20T05:00:00Z",
    ends_at: "2026-11-20T07:00:00Z",
    note: "Aircon repair",
    reason: "maintenance",
    affects: [],
    ...overrides,
  };
  db.blocks.push(block);
  return block;
}

/** US13 AC 4: what the evaluation of `booking` finds; by default nothing stands in its way. */
export function setEvaluation(booking: VenueBooking, found: Partial<Pick<BookingEvaluation, "conflicts" | "outside_hours">>) {
  db.evaluations[booking.id] = { conflicts: found.conflicts ?? [], outside_hours: found.outside_hours ?? null };
}

export function seedEquipmentType(name: string): FakeEquipmentType {
  const equipmentType = { id: newId("equipment-type"), name };
  db.equipmentTypes.push(equipmentType);
  return equipmentType;
}

/** An event that can take equipment lines: confirmed and assigned to the coordinator the tests act as. */
export function seedEquipmentEvent(overrides: Partial<FakeEquipmentEvent> = {}): FakeEquipmentEvent {
  const event: FakeEquipmentEvent = {
    id: newId("equipment-event"),
    name: "Equipment Request Demo",
    // Singapore 10:00 on 7 Nov 2026.
    start_at: "2026-11-07T02:00:00Z",
    status: "confirmed",
    coordinator_id: COORDINATOR_ID,
    ...overrides,
  };
  db.equipmentEvents.push(event);
  return event;
}

export function seedEquipmentLine(
  event: FakeEquipmentEvent,
  equipmentType: FakeEquipmentType,
  overrides: Partial<FakeEquipmentLine> = {},
): FakeEquipmentLine {
  const line: FakeEquipmentLine = {
    id: newId("equipment-line"),
    event: { id: event.id, name: event.name, start_at: event.start_at },
    equipment_type: equipmentType,
    quantity: 2,
    notes: null,
    status: "pending",
    review_note: null,
    requested_by_user_id: COORDINATOR_ID,
    reviewed_by_user_id: null,
    reviewed_at: null,
    availability_check: null,
    reservation: null,
    created_at: `2026-10-01T02:00:${String(db.nextId).padStart(2, "0")}Z`,
    updated_at: "2026-10-01T02:00:00Z",
    ...overrides,
  };
  db.equipmentLines.push(line);
  return line;
}

/**
 * What checking `line` finds (US5, SCRUM-125). The API works out availability, not the fake, so a test
 * says what it should be: by default everything requested is available, out of 10 with no location.
 */
export function setAvailability(line: FakeEquipmentLine, found: Partial<FakeAvailability> = {}): FakeAvailability {
  const available = found.available ?? 10;
  const result: FakeAvailability = {
    line_id: line.id,
    equipment_type: { id: line.equipment_type.id, name: line.equipment_type.name, storage_location: null },
    window: { starts_at: line.event.start_at ?? "2026-11-07T02:00:00Z", ends_at: "2026-11-07T05:00:00Z" },
    requested: line.quantity,
    total: 10,
    out_of_service: 0,
    reserved_elsewhere: 0,
    available,
    sufficient: available >= line.quantity,
    shortfall: Math.max(line.quantity - available, 0),
    ...found,
  };
  db.availability[line.id] = result;
  return result;
}

/**
 * Reserving `line` is refused for want of stock (US27, SCRUM-131): the API counts availability, not the
 * fake, so a test says when it falls short. By default a reservation fits.
 */
export function refuseReservation(line: FakeEquipmentLine, available: number): void {
  db.reservationShortfalls[line.id] = { available, requested: line.quantity, shortfall: line.quantity - available };
}

/** An active Tech support user (US14). Who's busy on an overlapping event is the API's to work out (D81). */
export function seedTechStaff(name: string): FakePerson {
  const person = { id: newId("tech-staff"), name };
  db.techStaff.push(person);
  return person;
}

/** Each assign or unassign a minute after the last, so the log's order is clear. */
function techStaffStamp(): string {
  const minute = db.techStaffRows.reduce((count, row) => count + (row.unassigned_at ? 2 : 1), 0);
  return `2026-10-02T04:${String(minute).padStart(2, "0")}:00Z`;
}

/** `staff` assigned to `event` by the coordinator the tests act as. */
export function seedTechStaffAssignment(event: FakeEquipmentEvent, staff: FakePerson): void {
  db.techStaffRows.push({
    event_id: event.id,
    staff,
    assigned_by: COORDINATOR_PERSON,
    assigned_at: techStaffStamp(),
    unassigned_by: null,
    unassigned_at: null,
  });
}

/** The venues the next search returns, in that order: the API decides which venues fit, not the fake. */
export function nextSearchResult(venues: Venue[]) {
  db.searchResult = venues;
}

/** An event the given managing roles see (US28), with what its registrations call returns. */
export function seedManagedEvent(
  overrides: Partial<EventRegistrations> = {},
  roles: ("organiser" | "coordinator")[] = ["organiser", "coordinator"],
): EventRegistrations {
  const managed: EventRegistrations = {
    event: {
      id: newId("event"),
      name: "Design Sprint Bootcamp",
      start_at: "2026-10-05T14:00:00+08:00",
      end_at: "2026-10-05T16:00:00+08:00",
      status: "confirmed",
      capacity: 2,
    },
    totals: { confirmed: 0, waitlisted: 0, offered: 0, seats_remaining: 2 },
    registration_fields: [],
    registrations: [],
    ...overrides,
  };
  roles.forEach((role) => db.managedEvents[role].push(managed));
  return managed;
}

/** A planning event the coordinator can edit (US12); pass `status` for one that can't be. */
export function seedSession(request: EventRequest, overrides: Partial<FakeSession> = {}): FakeSession {
  const session: FakeSession = {
    id: newId("session"),
    event_id: request.id,
    title: "Opening keynote",
    session_type: "presentation",
    speaker_name: "Dr Tan",
    starts_at: "2026-11-20T14:00:00+08:00",
    ends_at: "2026-11-20T15:00:00+08:00",
    outside_window: false,
    ...overrides,
  };
  db.sessions.push(session);
  return session;
}

/** US29b (SCRUM-143): a change request on `event`, the organiser's unless `requested_by_user_id` says otherwise. */
export function seedChangeRequest(
  event: EventRequest,
  overrides: Partial<FakeChangeRequest> & Pick<FakeChangeRequest, "changes">,
): FakeChangeRequest {
  const request: FakeChangeRequest = {
    id: newId("change-request"),
    event_id: event.id,
    event_name: event.name,
    request_reference: event.request_reference,
    status: "pending_approval",
    reason: null,
    created_at: new Date(Date.UTC(2026, 9, 1, 1, db.nextId)).toISOString(),
    requested_by_user_id: event.created_by_user_id ?? ORGANISER_ID,
    decided_at: null,
    decided_by: null,
    rejection_reason: null,
    ...overrides,
  };
  db.changeRequests.unshift(request);
  return request;
}

/** US29b (SCRUM-143): a review flag on `event`; `label` names its booking or line (null for registrations). */
export function seedReviewFlag(
  event: EventRequest,
  { label = "VB-2026-000001 · Seminar Room", ...overrides }: Partial<ReviewFlag> & { label?: string | null } = {},
): ReviewFlag {
  const flag: ReviewFlag = {
    id: newId("review-flag"),
    event_id: event.id,
    kind: "venue_booking",
    target: label === null ? null : { id: newId("target"), label, status: "approved" },
    fields: ["start_at", "end_at"],
    change_request_id: "change-request-seeded",
    raised_at: "2026-10-02T02:00:00Z",
    cleared_at: null,
    cleared_by: null,
    cleared_note: null,
    resolved: false,
    open: true,
    ...overrides,
  };
  db.reviewFlags.push(flag);
  return flag;
}

export function seedCoordinatedEvent(overrides: Partial<EventDetails> = {}): EventDetails {
  const event: EventDetails = {
    id: newId("event"),
    name: "Event Planning Demo",
    status: "planning",
    editable: (overrides.status ?? "planning") === "planning",
    start_at: "2026-10-21T10:00:00+08:00",
    end_at: "2026-10-21T12:00:00+08:00",
    request_reference: null,
    event_category: "Workshop",
    purpose: "Seeded for editing an event in planning (US12)",
    room_layout_preference: "Classroom",
    accessibility_needs: null,
    equipment_needs: null,
    join_link: null,
    capacity: 80,
    expected_attendees: 60,
    delivery_mode: "in_person",
    venue_name: "SMU SCIS Building",
    room_number: "Seminar Room 2-1",
    pending_change_requests: [],
    ...overrides,
  };
  db.coordinatedEvents.push(event);
  db.history[event.id] = [];
  return event;
}

/** Calls the screens made, optionally narrowed by method and path. */
export function callsTo(method: string, path: string | RegExp): RecordedCall[] {
  return db.calls.filter(
    (call) => call.method === method && (typeof path === "string" ? call.path === path : path.test(call.path)),
  );
}

// --- Rules ----------------------------------------------------------------------------------

function error(status: number, code: string, extra: Record<string, JsonBodyType> = {}) {
  return HttpResponse.json({ code, ...extra }, { status });
}

const DAY = 24 * 60 * MINUTE;

/** Exactly YYYY-MM-DD, and a day that exists (the calendar's INVALID_DATE_RANGE, deviation 51). */
function isCalendarDay(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function occupancy(event: FakeEvent): number {
  return db.registrations.filter((r) => r.event_id === event.id && (r.status === "confirmed" || r.status === "offered"))
    .length;
}

function seatsRemaining(event: FakeEvent): number {
  return Math.max(event.capacity - occupancy(event), 0);
}

function waitlistPosition(registration: FakeRegistration): number {
  const queue = db.registrations
    .filter((r) => r.event_id === registration.event_id && r.status === "waitlisted")
    .sort((a, b) => a.joined - b.joined);
  return queue.indexOf(registration) + 1;
}

function activeFor(eventId: string, attendeeId: string) {
  // An expired offer (SCRUM-137) holds nothing, so it isn't active.
  return db.registrations.find((r) => r.event_id === eventId && r.attendee_id === attendeeId && r.status !== "expired");
}

function confirmationBody(registration: FakeRegistration) {
  const event = db.events.find((e) => e.id === registration.event_id)!;
  return {
    registration_id: registration.id,
    status: "confirmed",
    event: {
      name: event.name,
      start_at: event.start_at,
      end_at: event.end_at,
      venue_name: event.venue_name,
      join_link: event.join_link,
    },
  };
}

function myRow(registration: FakeRegistration) {
  const event = db.events.find((e) => e.id === registration.event_id)!;
  return {
    registration_id: registration.id,
    event_id: event.id,
    event_name: event.name,
    date: event.start_at.slice(0, 10),
    start_time: event.start_at.slice(11, 16),
    end_time: event.end_at.slice(11, 16),
    venue_name: event.venue_name,
    joining_info: event.delivery_mode === "online" ? event.join_link : event.room_number,
    delivery_mode: event.delivery_mode,
  };
}

function byStart(a: FakeRegistration, b: FakeRegistration) {
  const ea = db.events.find((e) => e.id === a.event_id)!;
  const eb = db.events.find((e) => e.id === b.event_id)!;
  return ea.start_at.localeCompare(eb.start_at) || ea.name.localeCompare(eb.name);
}

const ROLES: Record<string, "organiser" | "coordinator" | "coordinator_lead" | "venue_staff" | "tech_support" | "safety_officer"> = {
  [ORGANISER_ID]: "organiser",
  [COORDINATOR_ID]: "coordinator",
  [LEAD_ID]: "coordinator_lead",
  [VENUE_STAFF_ID]: "venue_staff",
  [TECH_SUPPORT_ID]: "tech_support",
  [SAFETY_OFFICER_ID]: "safety_officer",
};

/** `get_current_user`: the role behind X-User-Id, or null for 401. */
function userRole(request: Request) {
  return ROLES[request.headers.get("X-User-Id") ?? ""] ?? null;
}

function nextReference(): string {
  return `ER-2026-${String(db.nextReference++).padStart(6, "0")}`;
}

const MANDATORY: (keyof EventRequestWrite)[] = [
  "name",
  "event_category",
  "purpose",
  "preferred_dates",
  "preferred_start_time",
  "preferred_end_time",
  "expected_attendees",
];

function missingFields(request: EventRequest): string[] {
  return MANDATORY.filter((field) => {
    const value = request[field];
    return value === null || value === "" || (Array.isArray(value) && value.length === 0);
  });
}

// D11 and D48 (SCRUM-120): the owner always; a Lead once it's past draft; a coordinator only the ones
// assigned to them now.
function visibleTo(request: EventRequest, role: string, userId: string) {
  if (role === "organiser") return request.created_by_user_id === userId;
  if (role === "coordinator") return request.status !== "draft" && request.coordinator?.id === userId;
  return request.status !== "draft";
}

// GET /event-requests/{id}'s own rule (request_service._can_read): its creator; past the request stage
// (COORDINATOR_EVENT_STATUSES) only its assigned coordinator, so a Lead gets 404 on a Planning or Confirmed event;
// at the request stage a Lead or its assigned coordinator.
const COORDINATOR_EVENT_STATUSES = new Set(["planning", "confirmed", "preparation", "cancelled"]);
const SUBMITTED_REQUEST_STATUSES = new Set(["submitted", "under_review", "awaiting_clarification", "approved", "rejected"]);

function readableBy(request: EventRequest, role: string, userId: string) {
  if (request.created_by_user_id === userId) return true;
  if (request.status === "draft") return false;
  const assigned = request.coordinator?.id === userId;
  if (COORDINATOR_EVENT_STATUSES.has(request.status)) return assigned;
  if (!SUBMITTED_REQUEST_STATUSES.has(request.status)) return false;
  return role === "coordinator_lead" || (role === "coordinator" && assigned);
}

// Who may open a request and its thread at all (SCRUM-120, D54): other roles get 403.
const REQUEST_READERS = new Set(["organiser", "coordinator", "coordinator_lead"]);

// SCRUM-13: who the Lead can pick, as GET /api/v1/coordinators returns them.
export const COORDINATOR_PERSON = { id: COORDINATOR_ID, name: "Casey Tan", email: "casey.tan@smu.edu.sg" };
// SCRUM-67, D30: the statuses a coordinator is actively working an event through.
const WORKLOAD_STATUSES = new Set(["under_review", "awaiting_clarification", "approved", "planning"]);
export const LEAD_PERSON = { id: LEAD_ID, name: "Lena Lead", email: "lena.lead@smu.edu.sg" };
const ORGANISER_PERSON = { id: ORGANISER_ID, name: "Olivia Organiser", email: "event.organiser@smu.edu.sg" };

const CLARIFIABLE = new Set(["submitted", "under_review"]);

// US18: the coordinator the readiness, confirmation and preparation routes act for (D48): anyone else's
// event, a draft or an unknown id is 404, other roles 403.
function confirmableBy(request: Request, id: string): EventRequest | Response {
  const role = userRole(request);
  if (!role) return error(401, "UNAUTHENTICATED");
  if (role !== "coordinator") return error(403, "FORBIDDEN");
  const found = db.requests.find((r) => r.id === id);
  if (!found || found.status === "draft" || !assignedTo(found, request.headers.get("X-User-Id")!)) {
    return error(404, "NOT_FOUND");
  }
  return found;
}

// US18 AC 1, 2: each live booking approved, the equipment lines approved, the safety check approved.
// --- US29b (SCRUM-143): change request decisions, by the rules backend/tests/event/test_change_request_decisions.py
// proves for app/event/change_decision_service.py: significant fields and what each flags (D103, D104), Planning
// and the safety approval only once the event is being arranged (D105, D106), and stale requests refused (D107).
type FlagKind = ReviewFlag["kind"];
const SCHEDULE_KINDS: FlagKind[] = ["venue_booking", "equipment_reservation", "registrations"];
const SIGNIFICANT_FIELDS: Record<string, FlagKind[]> = {
  start_at: SCHEDULE_KINDS,
  end_at: SCHEDULE_KINDS,
  preferred_dates: SCHEDULE_KINDS,
  preferred_start_time: SCHEDULE_KINDS,
  preferred_end_time: SCHEDULE_KINDS,
  expected_attendees: ["venue_booking", "registrations"],
  capacity: ["venue_booking", "registrations"],
  room_layout_preference: ["venue_booking"],
  accessibility_needs: ["venue_booking"],
  delivery_mode: ["venue_booking", "registrations"],
  equipment_needs: ["equipment_reservation"],
};
const ARRANGED = ["approved", "planning", "confirmed"];
const NOT_APPROVABLE = ["preparation", "cancelled", "completed", "rejected"];
const DECIDED_AT = "2026-10-02T03:00:00Z";

function requesterOf(request: FakeChangeRequest, event: EventRequest): string {
  return request.requested_by_user_id ?? event.created_by_user_id ?? ORGANISER_ID;
}

function personFor(id: string) {
  return [ORGANISER_PERSON, COORDINATOR_PERSON, LEAD_PERSON].find((person) => person.id === id) ?? { id, name: id, email: "" };
}

function sameValue(field: string, a: unknown, b: unknown): boolean {
  if ((field === "start_at" || field === "end_at") && typeof a === "string" && typeof b === "string") return Date.parse(a) === Date.parse(b);
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

function significantFields(request: FakeChangeRequest): string[] {
  return request.changes.map((c) => c.field).filter((field) => field in SIGNIFICANT_FIELDS);
}

function liveBookingsOf(event: EventRequest) {
  return db.bookings.filter((b) => b.event.id === event.id && (b.status === "requested" || b.status === "approved"));
}

function reservedLinesOf(event: EventRequest) {
  return db.equipmentLines.filter((line) => line.event.id === event.id && line.reservation !== null);
}

// The API's labels (backend/app/event/change_decision_service.py LABELS: US29a's, then US12's).
const CHANGE_LABELS: Record<string, string> = {
  name: "Event name",
  event_category: "Category",
  purpose: "Purpose",
  preferred_dates: "Preferred dates",
  preferred_start_time: "Preferred start time",
  preferred_end_time: "Preferred end time",
  start_at: "Start time",
  end_at: "End time",
  capacity: "Capacity",
  expected_attendees: "Expected attendance",
  delivery_mode: "Delivery mode",
  room_layout_preference: "Room layout",
  accessibility_needs: "Accessibility needs",
  equipment_needs: "Equipment needs",
  join_link: "Join link",
};

function changeView(request: FakeChangeRequest): ChangeRequestReview {
  const event = db.requests.find((r) => r.id === request.event_id)!;
  const current = event as unknown as Record<string, unknown>;
  const pending = request.status === "pending_approval";
  const significant = significantFields(request);
  const kinds = new Set(significant.flatMap((field) => SIGNIFICANT_FIELDS[field]));
  const impact = !pending
    ? null
    : significant.length === 0
      ? { status_after: event.status, venue_bookings: 0, equipment_reservations: 0, registrations: 0, safety_review_required: false }
      : !ARRANGED.includes(event.status)
        ? { status_after: event.status, venue_bookings: null, equipment_reservations: null, registrations: null, safety_review_required: null }
        : {
            status_after: event.status === "confirmed" ? "planning" : event.status,
            venue_bookings: kinds.has("venue_booking") ? liveBookingsOf(event).length : 0,
            equipment_reservations: kinds.has("equipment_reservation") ? reservedLinesOf(event).length : 0,
            registrations: 0,
            safety_review_required: event.safety_approved_at !== null,
          };
  return {
    id: request.id,
    event_id: event.id,
    event_name: event.name,
    request_reference: event.request_reference,
    event_status: event.status,
    source: requesterOf(request, event) === event.created_by_user_id ? "organiser" : "coordinator",
    requested_by: personFor(requesterOf(request, event)),
    reason: request.reason,
    status: request.status,
    created_at: request.created_at,
    changes: request.changes.map((c) => ({
      ...c,
      label: CHANGE_LABELS[c.field] ?? c.field,
      current_value: current[c.field] ?? null,
      stale: pending && !sameValue(c.field, c.old_value, current[c.field]),
    })),
    significant: significant.length > 0,
    impact,
    decided_at: request.decided_at ?? null,
    decided_by: request.decided_by ?? null,
    rejection_reason: request.rejection_reason ?? null,
  };
}

/** D102: the event's coordinator decides what they didn't make; a Lead (SCRUM-144) decides the coordinator's own edit. */
function decides(role: string, userId: string | null, request: FakeChangeRequest, event: EventRequest): boolean {
  const requester = requesterOf(request, event);
  if (role === "coordinator") return event.coordinator?.id === userId && requester !== userId;
  return requester !== event.created_by_user_id && requester === event.coordinator?.id && requester !== userId;
}

/** The change request this user decides (D102), or the refusal. */
function decidableBy(request: Request, id: string): FakeChangeRequest | Response {
  const role = userRole(request);
  if (role !== "coordinator" && role !== "coordinator_lead") return error(403, "FORBIDDEN");
  const userId = request.headers.get("X-User-Id");
  const found = db.changeRequests.find((r) => r.id === id);
  const event = found && db.requests.find((r) => r.id === found.event_id);
  if (!found || !event) return error(404, "NOT_FOUND");
  const own = requesterOf(found, event) === userId && (event.coordinator?.id === userId || role === "coordinator_lead");
  if (own) return error(403, "SELF_DECISION_NOT_ALLOWED");
  if (!decides(role, userId, found, event)) return error(404, "NOT_FOUND");
  return found;
}

/** Who a decision names: the Lead when a Lead decided (SCRUM-144), otherwise the coordinator. */
function deciderOf(request: Request) {
  const person = userRole(request) === "coordinator_lead" ? LEAD_PERSON : COORDINATOR_PERSON;
  return { id: person.id, name: person.name };
}

function historyEntry(request: FakeChangeRequest, action: string, field: string, previous: unknown, next: unknown): AuditEntry {
  return {
    id: newId("history"),
    field,
    previous_value: previous,
    new_value: next,
    user: { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name },
    created_at: DECIDED_AT,
    change_request_id: request.id,
    change_request_status: request.status,
    action,
  };
}

function raiseFlags(event: EventRequest, request: FakeChangeRequest, significant: string[]): ReviewFlag[] {
  const fieldsFor = (kind: FlagKind) => significant.filter((field) => SIGNIFICANT_FIELDS[field].includes(kind));
  const targets: [FlagKind, { id: string; label: string; status: string }][] = [];
  if (fieldsFor("venue_booking").length > 0) {
    for (const b of liveBookingsOf(event)) targets.push(["venue_booking", { id: b.id, label: `${b.reference} · ${b.venue.name}`, status: b.status }]);
  }
  if (fieldsFor("equipment_reservation").length > 0) {
    for (const line of reservedLinesOf(event)) {
      targets.push(["equipment_reservation", { id: line.id, label: `${line.equipment_type.name} × ${line.quantity}`, status: "reserved" }]);
    }
  }
  return targets.map(([kind, target]) => {
    const open = db.reviewFlags.find((f) => f.cleared_at === null && f.kind === kind && f.target?.id === target.id);
    if (open) {
      open.fields = [...open.fields, ...fieldsFor(kind).filter((field) => !open.fields.includes(field))];
      return open;
    }
    const flag: ReviewFlag = {
      id: newId("review-flag"),
      event_id: event.id,
      kind,
      target,
      fields: fieldsFor(kind),
      change_request_id: request.id,
      raised_at: DECIDED_AT,
      cleared_at: null,
      cleared_by: null,
      cleared_note: null,
      resolved: false,
      open: true,
    };
    db.reviewFlags.push(flag);
    return flag;
  });
}

function flagsOf(eventId: string): ReviewFlag[] {
  // Open first, then newest (app/event/review_flag_service.py).
  return db.reviewFlags
    .filter((f) => f.event_id === eventId)
    .sort((a, b) => Number(b.open) - Number(a.open) || b.raised_at.localeCompare(a.raised_at));
}

function readinessOf(event: EventRequest) {
  const items: { kind: "venue" | "equipment" | "technical_support" | "safety" | "review_flags"; name: string; complete: boolean; detail: string }[] = [];
  const live = db.bookings.filter((b) => b.event.id === event.id && (b.status === "requested" || b.status === "approved"));
  for (const booking of live) {
    const approved = booking.status === "approved";
    // US23a (SCRUM-90, D113): a booking needing rearrangement is outstanding, approved or not.
    const flagged = rearrangementOf(booking) !== undefined;
    items.push({
      kind: "venue",
      name: `${booking.venue.name}, ${booking.purpose ?? "Main venue"}`,
      complete: approved && !flagged,
      detail: flagged
        ? `Booking ${booking.reference} needs rearrangement: the venue has become unavailable.`
        : approved
          ? `Booking ${booking.reference} is approved.`
          : `Booking ${booking.reference} is waiting for Venue staff to approve it.`,
    });
  }
  if (live.length === 0) items.push({ kind: "venue", name: "Venue", complete: false, detail: "No venue has been requested yet." });
  const primaries = live.filter((b) => b.is_primary).length;
  if (live.length > 0 && primaries !== 1) {
    items.push({
      kind: "venue",
      name: "Primary venue",
      complete: false,
      detail: primaries === 0 ? "Choose which venue attendees see as the primary one." : "More than one venue is marked primary.",
    });
  }
  const allocated = live.reduce((sum, b) => sum + b.expected_attendees, 0);
  if (live.length > 0 && event.expected_attendees !== null && allocated < event.expected_attendees) {
    items.push({
      kind: "venue",
      name: "Attendance allocated",
      complete: false,
      detail: `The venues hold ${allocated} of the ${event.expected_attendees} expected attendees.`,
    });
  }
  const lines = db.equipmentLines.filter((l) => l.event.id === event.id && l.status !== "rejected");
  const approvedLines = lines.filter((l) => l.status === "approved");
  const pending = lines.length - approvedLines.length;
  const unreserved = approvedLines.filter((l) => !l.reservation).length;
  const noun = lines.length === 1 ? "line" : "lines";
  items.push({
    kind: "equipment",
    name: "Equipment",
    complete: pending === 0 && unreserved === 0,
    detail:
      lines.length === 0
        ? "No equipment was requested."
        : pending > 0
          ? `${pending} of ${lines.length} equipment ${noun} ${pending === 1 ? "is" : "are"} waiting for Tech support to approve.`
          : unreserved > 0
            ? `${unreserved} of ${lines.length} approved equipment ${noun} ${unreserved === 1 ? "is" : "are"} not reserved yet.`
            : "Every equipment line is approved and reserved.",
  });
  const staff = db.techStaffRows.filter((row) => row.event_id === event.id && row.unassigned_at === null).length;
  items.push({
    kind: "technical_support",
    name: "Technical support",
    complete: approvedLines.length === 0 || staff > 0,
    detail:
      approvedLines.length === 0
        ? "No technical support was requested."
        : staff > 0
          ? `${staff} Tech support staff ${staff === 1 ? "member is" : "members are"} assigned.`
          : "No Tech support staff member is assigned yet.",
  });
  const safe = event.safety_approved_at !== null;
  items.push({
    kind: "safety",
    name: "Safety check",
    complete: safe,
    detail: safe
      ? "Approved by the Safety Officer."
      : safetyStateOf(event) === "rejected"
        ? `Rejected by the Safety Officer: ${reviewsOf(event)[0].comments} Revise the arrangement, then send it for another review.`
        : safetyStateOf(event) === "changes_requested"
          ? `The Safety Officer asked for changes to ${SAFETY_CHANGE_AREAS.filter(([key]) => reviewsOf(event)[0].areas?.includes(key))
              .map(([, label]) => label)
              .join(", ")}: ${reviewsOf(event)[0].comments} Make the changes, then mark them done.`
          : "Waiting for the Safety Officer's approval.",
  });
  // US29b (SCRUM-143, D104): once flagged, every flag must be reviewed before confirming.
  const flags = flagsOf(event.id);
  if (flags.length > 0) {
    const open = flags.filter((f) => f.open).length;
    items.push({
      kind: "review_flags",
      name: "Review after change",
      complete: open === 0,
      detail: open === 0 ? "Every flagged arrangement is reviewed." : `${open} arrangement${open === 1 ? "" : "s"} to review after an approved change.`,
    });
  }
  return { ready: items.every((i) => i.complete), items };
}

// US30a: the checklist, as backend/app/safety/models.py has it, and the state the routes derive.
const SAFETY_CHECKLIST: [string, string][] = [
  ["attendance_capacity", "Expected attendance against venue capacity"],
  ["layout", "Room layout"],
  ["emergency_access", "Emergency access"],
  ["accessibility", "Accessibility"],
  ["equipment_placement", "Equipment placement"],
  ["crowd_movement", "Expected crowd movement"],
  ["venue_restrictions", "Known venue restrictions"],
];
// US30b: the areas a request for changes can mark, as backend/app/safety/models.py has them.
const SAFETY_CHANGE_AREAS: [string, string][] = [
  ["venue", "Venue"],
  ["layout", "Layout"],
  ["equipment", "Equipment"],
  ["accessibility", "Accessibility"],
  ["other", "Other"],
];
const REVIEWABLE = new Set(["approved", "planning"]);

function reviewsOf(event: EventRequest): FakeSafetyReview[] {
  return db.safetyReviews.filter((r) => r.event_id === event.id).sort((a, b) => b.created_at.localeCompare(a.created_at));
}

function safetyStateOf(event: EventRequest): "pending" | "approved" | "rejected" | "changes_requested" {
  if (event.safety_approved_at) return "approved";
  const latest = reviewsOf(event)[0];
  if ((latest?.outcome === "rejected" || latest?.outcome === "changes_requested") && !db.safetyResent[event.id]) return latest.outcome;
  return "pending";
}

function arrangementsReady(event: EventRequest): boolean {
  // AC 1: the venues and the equipment; technical support and the safety check aren't part of it.
  return readinessOf(event).items.every((item) => (item.kind !== "venue" && item.kind !== "equipment") || item.complete);
}

// What the Coordinator and Organiser read: a review without the Safety Officer's internal notes.
function publicReview({ internal_notes: _notes, ...review }: FakeSafetyReview) {
  return review;
}

// US22 after US10a (D20): may this user book, and list the bookings of, this event?
function assignedTo(request: EventRequest, userId: string): boolean {
  return request.coordinator?.id === userId;
}
// US26 (SCRUM-109): which events take lines, and the line checks, as app/equipment/service.py has them.
const EQUIPMENT_ELIGIBLE = new Set(["planning", "confirmed"]);
const LINE_FIELDS = ["equipment_type_id", "quantity"] as const;

function managedEquipmentEvent(request: Request, eventId: string): FakeEquipmentEvent | null {
  const event = db.equipmentEvents.find((e) => e.id === eventId);
  return event && event.status !== "draft" && event.coordinator_id === request.headers.get("X-User-Id") ? event : null;
}

/** INVALID_EQUIPMENT_LINE for the fields present in `values`, or null when they're all fine. */
function invalidLine(values: Record<string, unknown>): Response | null {
  const errors: Record<string, string> = {};
  if ("equipment_type_id" in values && !db.equipmentTypes.some((t) => t.id === values.equipment_type_id)) {
    errors.equipment_type_id = "Choose an equipment type from the catalogue.";
  }
  if ("quantity" in values && !(Number.isInteger(values.quantity) && (values.quantity as number) >= 1)) {
    errors.quantity = "Quantity must be a whole number of at least 1.";
  }
  const fields = LINE_FIELDS.filter((field) => field in errors);
  return fields.length ? error(422, "INVALID_EQUIPMENT_LINE", { fields, errors }) : null;
}

function duplicateLine(eventId: string, typeId: unknown, lineId?: string): Response | null {
  const live = db.equipmentLines.some(
    (l) => l.event.id === eventId && l.equipment_type.id === typeId && l.status !== "rejected" && l.id !== lineId,
  );
  return live
    ? error(409, "DUPLICATE_EQUIPMENT_TYPE", {
        fields: ["equipment_type_id"],
        message: "This event already has a pending or approved line for that equipment type. Change its quantity instead.",
      })
    : null;
}

// US14 (SCRUM-134): GET /events/{id}/tech-staff, and POST's answer. D80: an approved line, on a planning
// or confirmed event.
function techStaffBody(event: FakeEquipmentEvent) {
  const eligible =
    EQUIPMENT_ELIGIBLE.has(event.status) && db.equipmentLines.some((l) => l.event.id === event.id && l.status === "approved");
  const rows = db.techStaffRows.filter((row) => row.event_id === event.id);
  const active = rows.filter((row) => !row.unassigned_at);
  const assignedIds = new Set(active.map((row) => row.staff.id));
  const log = rows
    .flatMap((row) => [
      { action: "assigned", staff: row.staff, by: row.assigned_by, at: row.assigned_at },
      ...(row.unassigned_at ? [{ action: "unassigned", staff: row.staff, by: row.unassigned_by!, at: row.unassigned_at }] : []),
    ])
    .sort((a, b) => b.at.localeCompare(a.at));
  return {
    eligible,
    assigned: active.map(({ staff, assigned_by, assigned_at }) => ({ staff, assigned_by, assigned_at })),
    available: eligible
      ? db.techStaff.filter((p) => !assignedIds.has(p.id)).sort((a, b) => a.name.localeCompare(b.name))
      : [],
    log,
  };
}

function cleanNotes(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

// US24 (SCRUM-128): a purpose too (D66).
// US24 (D71): the Organiser reads an event's venues once its request is approved.
const ORGANISER_VISIBLE = ["approved", "planning", "confirmed", "cancelled", "completed"];

function isLive(booking: VenueBooking): boolean {
  return booking.status === "requested" || booking.status === "approved";
}

/** US23b (SCRUM-91, D117): a booking's requested or approved replacement, if any. */
function liveReplacementOf(booking: VenueBooking): VenueBooking | undefined {
  return db.bookings.find((b) => b.replaces_booking_id === booking.id && isLive(b));
}

/** US23a (SCRUM-90): the block that left this live booking or hold needing rearrangement, if any (D113). */
function rearrangementOf(booking: VenueBooking): FakeVenueBlock | undefined {
  if (!isLive(booking) && booking.status !== "held") return undefined;
  return db.blocks.find((block) => block.affects.includes(booking.id));
}

const BOOKING_REQUIRED = ["event_id", "venue_id", "starts_at", "ends_at", "expected_attendees", "room_layout", "purpose"];
const SECTION_ORDER = ["details", "schedule", "attendance", "layout", "accessibility", "equipment", "registration"];

// US15 (D93, D95, D96): the agenda's rules the fake keeps.
const AGENDA_EDITABLE = ["draft", "planning"];

function ownRequest(request: Request, id: string): EventRequest | undefined {
  return db.requests.find((r) => r.id === id && r.created_by_user_id === request.headers.get("X-User-Id"));
}

function agendaOf(eventId: string): FakeSession[] {
  const at = (iso: string) => new Date(iso).getTime();
  return db.sessions
    .filter((s) => s.event_id === eventId)
    .sort((a, b) => at(a.starts_at) - at(b.starts_at) || at(a.ends_at) - at(b.ends_at) || a.title.localeCompare(b.title));
}

function sessionValues(current: Partial<FakeSession>, body: unknown): Partial<FakeSession> {
  const sent = (body ?? {}) as Partial<FakeSession>;
  const merged = { ...current, ...sent };
  return {
    title: (merged.title ?? "").trim(),
    session_type: merged.session_type,
    speaker_name: merged.speaker_name?.trim() || null,
    starts_at: merged.starts_at,
    ends_at: merged.ends_at,
  };
}

function refuseSession(eventId: string, values: Partial<FakeSession>, sessionId?: string): Response | null {
  // As the API's schema: a time that's sent but isn't one ("") is FastAPI's own 422, with no `code`; only a
  // missing (null) time reaches the service's per-field messages.
  for (const field of ["starts_at", "ends_at"] as const) {
    const value = values[field];
    if (value != null && Number.isNaN(Date.parse(value))) {
      return HttpResponse.json({ detail: [{ type: "datetime_from_date_parsing", loc: ["body", field] }] }, { status: 422 });
    }
  }
  const errors: Record<string, string> = {};
  if (!values.title) errors.title = "Give the session a title.";
  if (!values.session_type) errors.session_type = "Choose a session type.";
  if (!values.speaker_name && values.session_type !== "break") errors.speaker_name = "Name the speaker or presenter. Only a break has none.";
  if (!values.starts_at) errors.starts_at = "Give the session's start time.";
  if (!values.ends_at) errors.ends_at = "Give the session's end time.";
  else if (values.starts_at && new Date(values.ends_at) <= new Date(values.starts_at)) errors.ends_at = "The end must be after the start.";
  if (Object.keys(errors).length > 0) return error(422, "INVALID_SESSION", { fields: Object.keys(errors), errors });
  const starts = new Date(values.starts_at!).getTime();
  const ends = new Date(values.ends_at!).getTime();
  const clash = agendaOf(eventId).find(
    (s) => s.id !== sessionId && new Date(s.starts_at).getTime() < ends && new Date(s.ends_at).getTime() > starts,
  );
  if (clash) {
    return error(409, "SESSION_OVERLAP", { session: { id: clash.id, title: clash.title, starts_at: clash.starts_at, ends_at: clash.ends_at } });
  }
  return null;
}

// US9 (SCRUM-12): asking (organiser) or cancelling directly (coordinator).
const CANCELLABLE_STATUSES = new Set(["approved", "planning", "confirmed", "preparation"]);

function cancellationTime(): string {
  return new Date(Date.UTC(2026, 9, 1, 1, db.nextId)).toISOString();
}

function startCancellation(event: EventRequest, body: unknown, direct: boolean) {
  if (!CANCELLABLE_STATUSES.has(event.status)) return error(409, "CANCELLATION_NOT_ALLOWED", { status: event.status });
  const reason = ((body ?? {}) as { reason?: string }).reason?.trim();
  if (!reason) return error(422, "MISSING_REQUIRED_FIELD", { fields: ["reason"] });
  const pending = db.cancellations.find((c) => c.event_id === event.id && c.status === "pending");
  if (pending) return error(409, "CANCELLATION_PENDING", { cancellation_id: pending.id });
  const now = cancellationTime();
  const person = direct ? { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name } : { id: ORGANISER_PERSON.id, name: ORGANISER_PERSON.name };
  if (direct) event.status = "cancelled";
  const created: Cancellation = {
    id: newId("cancellation"),
    event_id: event.id,
    event_name: event.name,
    request_reference: event.request_reference,
    event_status: event.status,
    status: direct ? "approved" : "pending",
    reason,
    requested_by: person,
    requested_at: now,
    decided_by: direct ? person : null,
    decided_at: direct ? now : null,
    rejection_reason: null,
    direct,
  };
  db.cancellations.unshift(created);
  return HttpResponse.json(created as unknown as JsonBodyType, { status: direct ? 200 : 201 });
}

// --- Handlers -------------------------------------------------------------------------------

type Resolver = (args: { request: Request; params: Record<string, string>; body: unknown }) =>
  | Response
  | Promise<Response>;

function route(method: "get" | "post" | "patch" | "delete", path: string, resolver: Resolver) {
  return http[method](`${API}${path}`, async ({ request, params }) => {
    const body: unknown = method === "get" || method === "delete" ? null : await request.clone().json().catch(() => null);
    const url = new URL(request.url);
    db.calls.push({ method: method.toUpperCase(), path: url.pathname, url, headers: request.headers, body });
    return resolver({ request, params: params as Record<string, string>, body });
  });
}

function attendeeOf(request: Request): string | null {
  const id = request.headers.get("X-Attendee-Id");
  return id === ATTENDEE_ID ? id : null;
}

const handlers = [
  route("get", "/api/events/health", () => HttpResponse.text("event service is up")),

  // Attendee routes (§3), identified by X-Attendee-Id.
  route("get", "/api/v1/events/available", ({ request }) => {
    const attendee = attendeeOf(request);
    if (!attendee) return error(401, "UNAUTHENTICATED");
    return HttpResponse.json({
      events: db.events.map((event) => {
        const seats = seatsRemaining(event);
        return {
          id: event.id,
          name: event.name,
          start_at: event.start_at,
          end_at: event.end_at,
          delivery_mode: event.delivery_mode,
          venue_name: event.venue_name,
          // US24 (D70): the API gives the primary venue's location, else room_number; these have no bookings.
          venue_location: event.delivery_mode === "online" ? null : event.room_number,
          join_link: event.join_link,
          capacity: event.capacity,
          seats_remaining: seats,
          is_full: seats === 0,
          waitlist_available: seats === 0 && event.waitlist_enabled,
          already_registered: activeFor(event.id, attendee) !== undefined,
          registration_fields: event.registration_fields,
        };
      }),
    });
  }),

  route("get", "/api/v1/me/registrations", ({ request }) => {
    const attendee = attendeeOf(request);
    if (!attendee) return error(401, "UNAUTHENTICATED");
    const mine = db.registrations.filter((r) => r.attendee_id === attendee).sort(byStart);
    return HttpResponse.json({
      confirmed: mine.filter((r) => r.status === "confirmed").map(myRow),
      waitlisted: mine
        .filter((r) => r.status === "waitlisted")
        .map((r) => ({ ...myRow(r), waitlist_position: waitlistPosition(r) })),
      offered: mine
        .filter((r) => r.status === "offered")
        .map((r) => ({ ...myRow(r), offer_expires_at: r.offer_expires_at })),
      // Not shown once the attendee is back on the event with an active row (§3).
      expired: mine
        .filter((r) => r.status === "expired" && !activeFor(r.event_id, attendee))
        .map((r) => ({ ...myRow(r), offer_expires_at: r.offer_expires_at })),
    });
  }),

  route("post", "/api/v1/events/:eventId/registrations", ({ request, params, body }) => {
    const attendee = attendeeOf(request);
    if (!attendee) return error(401, "UNAUTHENTICATED");
    const event = db.events.find((e) => e.id === params.eventId);
    if (!event) return error(404, "NOT_FOUND");
    if (activeFor(event.id, attendee)) return error(409, "ALREADY_REGISTERED");
    if (seatsRemaining(event) === 0) {
      return error(409, "EVENT_FULL", {
        waitlist_available: event.waitlist_enabled,
        message: event.waitlist_enabled ? "You may join the waitlist" : "This event is full.",
      });
    }
    const answers = (body as { answers?: Record<string, string> } | null)?.answers ?? {};
    const missing = event.registration_fields
      .filter((field) => field.required && !answers[field.field_key])
      .map((field) => field.field_key);
    if (missing.length > 0) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    const registration = seedRegistration(event, { attendee_id: attendee, answers });
    return HttpResponse.json(confirmationBody(registration), { status: 201 });
  }),

  // SCRUM-136 (D3, D7): the logged-in attendee joins; there's no body. An email-only place of
  // theirs from before is linked to them and answered ALREADY_REGISTERED, as the API does.
  route("post", "/api/v1/events/:eventId/waitlist", ({ request, params }) => {
    const attendee = attendeeOf(request);
    if (!attendee) return error(401, "UNAUTHENTICATED");
    const event = db.events.find((e) => e.id === params.eventId);
    if (!event) return error(404, "NOT_FOUND");
    if (db.registrations.some((r) => r.event_id === event.id && r.attendee_id === attendee)) {
      return error(409, "ALREADY_REGISTERED");
    }
    const emailOnly = db.registrations.find(
      (r) => r.event_id === event.id && r.attendee_id === null && r.email.toLowerCase() === ATTENDEE_EMAIL.toLowerCase(),
    );
    if (emailOnly) {
      emailOnly.attendee_id = attendee;
      return error(409, "ALREADY_REGISTERED");
    }
    if (!event.waitlist_enabled) return error(409, "WAITLIST_NOT_ENABLED");
    if (seatsRemaining(event) > 0) return error(409, "SEATS_AVAILABLE");
    const registration = seedRegistration(event, { attendee_id: attendee, email: ATTENDEE_EMAIL, status: "waitlisted" });
    return HttpResponse.json(
      { registration_id: registration.id, status: "waitlisted", position: waitlistPosition(registration) },
      { status: 201 },
    );
  }),

  route("post", "/api/v1/registrations/:id/withdraw", ({ request, params }) => {
    const attendee = attendeeOf(request);
    if (!attendee) return error(401, "UNAUTHENTICATED");
    const registration = db.registrations.find((r) => r.id === params.id && r.attendee_id === attendee);
    if (!registration) return error(404, "NOT_FOUND");
    const event = db.events.find((e) => e.id === registration.event_id)!;
    const freedSeat = registration.status === "confirmed";
    db.registrations = db.registrations.filter((r) => r !== registration);
    // TC-US7-07: a freed seat goes to the head of the queue as an offer.
    if (freedSeat) {
      const next = db.registrations
        .filter((r) => r.event_id === event.id && r.status === "waitlisted")
        .sort((a, b) => a.joined - b.joined)[0];
      if (next) Object.assign(next, { status: "offered", offer_expires_at: "2026-10-03T01:00:00Z" });
    }
    return HttpResponse.json({
      status: "withdrawn",
      withdrawn_at: "2026-10-01T02:05:00Z",
      event_name: event.name,
      seats_remaining: seatsRemaining(event),
    });
  }),

  route("post", "/api/v1/registrations/:id/accept", ({ request, params }) => {
    const attendee = attendeeOf(request);
    if (!attendee) return error(401, "UNAUTHENTICATED");
    const registration = db.registrations.find((r) => r.id === params.id && r.attendee_id === attendee);
    if (!registration) return error(404, "NOT_FOUND");
    if (registration.status !== "offered") return error(409, "NO_ACTIVE_OFFER");
    registration.status = "confirmed";
    delete registration.offer_expires_at;
    return HttpResponse.json(confirmationBody(registration));
  }),

  // Venues (US20, US2), identified by X-User-Id.
  route("get", "/api/v1/venues", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    const url = new URL(request.url);
    const q = (url.searchParams.get("q") ?? "").trim().toLowerCase();
    const venues = db.venues
      .filter((venue) => role === "venue_staff" || venue.is_active)
      .filter((venue) => !q || venue.name.toLowerCase().includes(q))
      .sort((a, b) => a.name.localeCompare(b.name));
    return HttpResponse.json({ venues });
  }),

  // US2 search (SCRUM-7). Deliberately no search rules here: capacity, hours and bookings are the
  // API's job, proven by backend/tests/venue/test_venue_search.py and e2e/tests/venue-search.spec.ts.
  // This returns the venues a test queues with `nextSearchResult`, echoing the criteria sent, so
  // integration tests check only what the screen sends and shows.
  route("get", "/api/v1/venues/available", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role === "organiser") return error(403, "FORBIDDEN");
    const url = new URL(request.url);
    const get = (key: string) => url.searchParams.get(key);
    const missing = ["date", "start_time", "end_time", "attendees"].filter((key) => !get(key));
    if (missing.length > 0) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    return HttpResponse.json({
      venues: db.searchResult,
      criteria: {
        date: get("date"),
        start_time: `${get("start_time")}:00`,
        end_time: `${get("end_time")}:00`,
        attendees: Number(get("attendees")),
        location: (get("location") ?? "").trim() || null,
        facilities: url.searchParams.getAll("facilities"),
        accessibility: url.searchParams.getAll("accessibility"),
      },
    });
  }),

  // US12 (SCRUM-15), identified by X-User-Id. Which fields are critical, the validation and the audit
  // log are the API's (backend/tests/event/test_event_edits.py); this saves non-critical fields, holds an
  // edit with a critical one, and logs each changed field, so a flow sees its own writes. A test queues a
  // refusal with server.use(...).
  route("get", "/api/v1/me/coordinated-events", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    return HttpResponse.json({
      events: db.coordinatedEvents.map(({ id, name, status, editable, start_at, end_at }) => ({ id, name, status, editable, start_at, end_at })),
    });
  }),

  route("get", "/api/v1/events/:eventId", ({ request, params }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const event = db.coordinatedEvents.find((e) => e.id === params.eventId);
    return event ? HttpResponse.json(event) : error(404, "NOT_FOUND");
  }),

  route("patch", "/api/v1/events/:eventId", ({ request, params, body }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const event = db.coordinatedEvents.find((e) => e.id === params.eventId);
    if (!event) return error(404, "NOT_FOUND");
    if (!event.editable) return error(409, "EVENT_NOT_EDITABLE", { status: event.status });
    const values = body as Record<string, unknown>;
    const record = event as unknown as Record<string, unknown>;
    const changes = Object.entries(values)
      .filter(([field, value]) => record[field] !== value)
      .map(([field, value]) => ({ field, old_value: record[field] ?? null, new_value: value }));
    const critical = changes.filter((c) => ["start_at", "end_at", "capacity", "expected_attendees", "delivery_mode"].includes(c.field));
    const now = new Date(Date.UTC(2026, 9, 1, 1, db.nextId)).toISOString();
    const requestId = critical.length ? newId("change-request") : null;
    if (requestId) {
      event.pending_change_requests = [
        { id: requestId, status: "pending_approval", changes, requested_by: { id: COORDINATOR_ID, name: "Casey Tan" }, created_at: now },
        ...event.pending_change_requests,
      ];
    } else {
      changes.forEach((c) => (record[c.field] = c.new_value));
    }
    const logged = changes.map((c) => ({
      id: newId("audit"),
      field: c.field,
      previous_value: c.old_value,
      new_value: c.new_value,
      user: { id: COORDINATOR_ID, name: "Casey Tan" },
      created_at: now,
      change_request_id: requestId,
      change_request_status: requestId ? ("pending_approval" as const) : null,
    }));
    db.history[event.id] = [...logged.reverse(), ...db.history[event.id]];
    return HttpResponse.json(
      {
        outcome: requestId ? "pending_approval" : "saved",
        message: requestId
          ? "Your change is awaiting approval. The event keeps its current details until then."
          : changes.length ? "Your changes are saved." : "Nothing changed, so nothing was saved.",
        event,
        change_request: requestId ? event.pending_change_requests[0] : null,
      } as unknown as JsonBodyType,
      { status: requestId ? 202 : 200 },
    );
  }),

  route("get", "/api/v1/events/:eventId/history", ({ request, params }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const entries = db.history[params.eventId];
    return entries ? HttpResponse.json({ entries } as unknown as JsonBodyType) : error(404, "NOT_FOUND");
  }),

  // US21 (SCRUM-88) venue calendar, by the rules backend/tests/venue/test_calendar.py proves for
  // app/venue/calendar_service.py: who (D56), the range (D61, deviation 51), an inactive venue as
  // GET /venues/{id} has it, live bookings by their occupied window with a cancelled event's included
  // (D57, D60), blocks, and the reference only for Venue staff, Leads and the event's coordinator (D58).
  route("get", "/api/v1/venues/:venueId/calendar", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator" && role !== "coordinator_lead" && role !== "venue_staff") return error(403, "FORBIDDEN");
    const url = new URL(request.url);
    const days: Record<string, string> = {};
    const bad: string[] = [];
    for (const field of ["from", "to"]) {
      const value = url.searchParams.get(field) ?? "";
      if (isCalendarDay(value)) days[field] = value;
      else bad.push(field);
    }
    if (bad.length === 0) {
      const span = (Date.parse(days.to) - Date.parse(days.from)) / DAY;
      if (!(span >= 0 && span < 42)) bad.push("to");
    }
    if (bad.length > 0) {
      return error(422, "INVALID_DATE_RANGE", {
        fields: bad,
        message: "Choose a from and to date (YYYY-MM-DD), to not before from, at most 42 days.",
      });
    }
    const userId = request.headers.get("X-User-Id");
    const live = (booking: VenueBooking) => booking.status === "requested" || booking.status === "approved";
    const coordinates = (booking: VenueBooking) =>
      db.requests.find((r) => r.id === booking.event.id)?.coordinator?.id === userId;
    const venue = db.venues.find((v) => v.id === params.venueId);
    const sees =
      venue &&
      (venue.is_active ||
        role === "venue_staff" ||
        role === "coordinator_lead" ||
        db.bookings.some((b) => b.venue.id === venue.id && live(b) && coordinates(b)));
    if (!venue || !sees) return error(404, "NOT_FOUND");

    const start = Date.parse(`${days.from}T00:00:00+08:00`);
    const end = Date.parse(`${days.to}T00:00:00+08:00`) + DAY;
    const overlaps = (startsAt: string, endsAt: string) => Date.parse(startsAt) < end && Date.parse(endsAt) > start;
    const seesEveryReference = role === "venue_staff" || role === "coordinator_lead";
    const bookings = db.bookings
      // US25 (SCRUM-93): a hold is drawn too, as kind "hold"; an expired one isn't listed (AC 6).
      .filter(
        (b) => b.venue.id === venue.id && (live(b) || b.status === "held") && overlaps(b.occupied_starts_at, b.occupied_ends_at),
      )
      .map((b) => ({
        kind: b.status === "held" ? "hold" : "booking",
        label: b.status === "held" ? "Hold" : "Booking",
        starts_at: b.starts_at,
        ends_at: b.ends_at,
        occupied: { starts_at: b.occupied_starts_at, ends_at: b.occupied_ends_at },
        booking: {
          id: b.id,
          reference: seesEveryReference || coordinates(b) ? b.reference : null,
          status: b.status,
          event: { name: b.event.name, request_reference: b.event.request_reference, status: b.event.status },
          // US24 (D73, D78): Venue staff set it from the calendar's dialog.
          preparation_status: b.preparation_status,
          hold_expires_at: b.hold_expires_at,
        },
        note: null,
      }));
    const blocks = db.blocks
      // An empty period (ended before it began, D118) overlaps nothing.
      .filter((block) => block.venue_id === venue.id && block.ends_at > block.starts_at && overlaps(block.starts_at, block.ends_at))
      .map((block) => ({
        kind: "block",
        block_id: block.id,
        ended_early_at: block.ended_early_at ?? null,
        label: "Unavailable",
        starts_at: block.starts_at,
        ends_at: block.ends_at,
        occupied: { starts_at: block.starts_at, ends_at: block.ends_at },
        booking: null,
        note: block.note,
        reason: block.reason,
      }));
    // By occupied start; a stable sort keeps bookings before blocks at the same start.
    const items = [...bookings, ...blocks].sort(
      (a, b) => Date.parse(a.occupied.starts_at) - Date.parse(b.occupied.starts_at),
    );
    const { id, name, is_active, opens_at, closes_at, setup_minutes, turnaround_minutes } = venue;
    return HttpResponse.json({
      venue: { id, name, is_active, opens_at, closes_at, setup_minutes, turnaround_minutes },
      from: days.from,
      to: days.to,
      items,
    });
  }),

  // Event registrations (US28, SCRUM-96), identified by X-User-Id. Like search, no rules here: who
  // manages which event and which rows a filter shows are the API's job, proven by
  // backend/tests/registration/test_event_registrations.py. These return what a test seeds with
  // `seedManagedEvent`, so integration tests check what the screen sends and shows.
  route("get", "/api/v1/me/managed-events", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "organiser" && role !== "coordinator") return error(403, "FORBIDDEN");
    return HttpResponse.json({ events: db.managedEvents[role].map((managed) => managed.event) });
  }),

  route("get", "/api/v1/events/:eventId/registrations", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "organiser" && role !== "coordinator") return error(403, "FORBIDDEN");
    const managed = db.managedEvents[role].find((m) => m.event.id === params.eventId);
    if (!managed) return error(404, "NOT_FOUND");
    return HttpResponse.json(managed);
  }),

  // US22 venue bookings (SCRUM-89), identified by X-User-Id. The contract and identity rules only:
  // overlap, capacity and venue warnings are the API's (backend/tests/venue/test_booking_api.py), so
  // a test queues a refusal or warnings with server.use(...).
  route("post", "/api/v1/venue-bookings", ({ request, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const sent = (body ?? {}) as Record<string, unknown>;
    const missing = BOOKING_REQUIRED.filter((field) => sent[field] === undefined || sent[field] === null || sent[field] === "");
    if (missing.length > 0) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    // D20 since US10a: only the event's assigned coordinator; anyone else's or an unassigned event is 404.
    const event = db.requests.find(
      (r) => r.id === sent.event_id && r.status !== "draft" && assignedTo(r, request.headers.get("X-User-Id")!),
    );
    const venue = db.venues.find((v) => v.id === sent.venue_id && v.is_active);
    if (!event || !venue) return error(404, "NOT_FOUND");
    if (event.status !== "approved" && event.status !== "planning") {
      return error(409, "EVENT_NOT_BOOKABLE", { status: event.status });
    }
    // US23b (SCRUM-91) AC 3 (D117): a replacement names a booking of this event that needs rearrangement, with no live
    // replacement yet. The rest (overlap, hours, capacity) is the API's (backend/tests/venue/test_replacement.py).
    const replaces = typeof sent.replaces_booking_id === "string" ? sent.replaces_booking_id : null;
    if (replaces) {
      const original = db.bookings.find((b) => b.id === replaces && b.event.id === event.id);
      if (!original) return error(422, "INVALID_BOOKING", { fields: ["replaces_booking_id"], errors: {} });
      if (!rearrangementOf(original)) return error(409, "BOOKING_NOT_REPLACEABLE", { status: original.status });
      const existing = liveReplacementOf(original);
      if (existing) {
        return error(409, "REPLACEMENT_EXISTS", {
          reference: existing.reference,
          message: `Booking ${existing.reference} is already the replacement. Withdraw it before requesting another.`,
        });
      }
    }
    const booking = seedBooking(event, venue, {
      replaces_booking_id: replaces,
      requested_by_user_id: request.headers.get("X-User-Id")!,
      starts_at: String(sent.starts_at),
      ends_at: String(sent.ends_at),
      expected_attendees: Number(sent.expected_attendees),
      room_layout: String(sent.room_layout),
      required_facilities: (sent.required_facilities as string[] | undefined) ?? [],
      required_accessibility_features: (sent.required_accessibility_features as string[] | undefined) ?? [],
      special_requirements: (sent.special_requirements as string | undefined) ?? null,
      purpose: String(sent.purpose).trim(),
      // D68: the event's first live booking is its primary venue.
      is_primary: !db.bookings.some(
        (b) => b.event.id === event.id && b.is_primary && (b.status === "requested" || b.status === "approved"),
      ),
    });
    return HttpResponse.json({ ...booking, warnings: [] }, { status: 201 });
  }),

  route("post", "/api/v1/venue-bookings/:id/withdraw", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const booking = db.bookings.find((b) => b.id === params.id);
    const userId = request.headers.get("X-User-Id");
    // US25: a hold was placed by Venue staff, so the event's coordinator declines it.
    const event = booking && db.requests.find((r) => r.id === booking.event.id);
    if (!booking || (booking.requested_by_user_id !== userId && !(event && assignedTo(event, userId!)))) {
      return error(404, "NOT_FOUND");
    }
    // US24 (D69): an approved booking can be withdrawn too, so the refusal says it isn't live; US25: a hold too.
    if (booking.status !== "requested" && booking.status !== "approved" && booking.status !== "held") {
      return error(409, "BOOKING_NOT_LIVE", { status: booking.status });
    }
    Object.assign(booking, { status: "withdrawn", withdrawn_at: "2026-10-01T03:00:00Z", updated_at: "2026-10-01T03:00:00Z" });
    return HttpResponse.json(booking);
  }),

  // US4 (SCRUM-8): Venue Staff decide a pending request as a whole. Whether the venue is free (with
  // buffers) is the API's rule (backend/tests/venue/test_booking_decision_api.py); a test queues a
  // VENUE_UNAVAILABLE refusal with server.use(...).
  ...(["approve", "reject"] as const).map((action) =>
    route("post", `/api/v1/venue-bookings/:id/${action}`, ({ request, params, body }) => {
      const role = userRole(request);
      if (!role) return error(401, "UNAUTHENTICATED");
      if (role !== "venue_staff") return error(403, "FORBIDDEN");
      const booking = db.bookings.find((b) => b.id === params.id);
      if (!booking) return error(404, "NOT_FOUND");
      // D51 (SCRUM-120): not a booking they requested, nor one for an event they coordinate.
      const userId = request.headers.get("X-User-Id");
      const event = db.requests.find((r) => r.id === booking.event.id);
      if (booking.requested_by_user_id === userId || event?.coordinator?.id === userId) {
        return error(403, "SELF_DECISION_NOT_ALLOWED");
      }
      if (booking.status !== "requested") return error(409, "BOOKING_NOT_PENDING", { status: booking.status });
      const notes = (body ?? {}) as { reason?: string; alternative_suggestion?: string };
      Object.assign(booking, {
        status: action === "approve" ? "approved" : "rejected",
        decided_at: "2026-10-01T03:00:00Z",
        decided_by_user_id: request.headers.get("X-User-Id"),
        updated_at: "2026-10-01T03:00:00Z",
        rejection_reason: action === "reject" ? (notes.reason ?? null) : null,
        alternative_suggestion: action === "reject" ? (notes.alternative_suggestion ?? null) : null,
      });
      return HttpResponse.json(booking);
    }),
  ),

  route("get", "/api/v1/venue-bookings/pending", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "venue_staff") return error(403, "FORBIDDEN");
    // Newest first, like the API (SCRUM-150).
    const pending = db.bookings.filter((b) => b.status === "requested").sort((a, b) => b.created_at.localeCompare(a.created_at));
    return HttpResponse.json({ bookings: pending });
  }),

  // US13 AC 4 (D36): Venue Staff only. Conflicts are the API's rule (backend/tests/venue/
  // test_buffer_api.py), so a test sets what this finds with setEvaluation; by default it's clear.
  route("get", "/api/v1/venue-bookings/:id/evaluation", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "venue_staff") return error(403, "FORBIDDEN");
    const booking = db.bookings.find((b) => b.id === params.id);
    if (!booking) return error(404, "NOT_FOUND");
    const found = db.evaluations[booking.id] ?? { conflicts: [], outside_hours: null };
    const evaluation: BookingEvaluation = {
      booking_id: booking.id,
      reference: booking.reference,
      occupied: { starts_at: booking.occupied_starts_at, ends_at: booking.occupied_ends_at },
      ...found,
      clear: found.conflicts.length === 0 && found.outside_hours === null,
    };
    return HttpResponse.json(evaluation);
  }),

  // US22, and since US24 (SCRUM-128) the event's Organiser too (D71), with whether its venues are
  // arranged (D67, D72), its primary (D68) and who acts next, by app/venue/booking_service.py's rules.
  route("get", "/api/v1/events/:id/venue-bookings", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator" && role !== "venue_staff" && role !== "organiser") return error(403, "FORBIDDEN");
    const userId = request.headers.get("X-User-Id")!;
    const event = db.requests.find((r) => r.id === params.id && r.status !== "draft");
    // Venue Staff read any event's bookings; a coordinator only those of an event assigned to them (D20);
    // the Organiser only their own, from approved on (D71).
    const allowed =
      event &&
      (role === "venue_staff" ||
        (role === "coordinator" && assignedTo(event, userId)) ||
        (role === "organiser" && event.created_by_user_id === userId && ORGANISER_VISIBLE.includes(event.status)));
    if (!event || !allowed) return error(404, "NOT_FOUND");
    const bookings = db.bookings
      .filter((b) => b.event.id === event.id)
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at))
      .map((b) => {
        const active = db.venues.find((v) => v.id === b.venue.id)?.is_active ?? true;
        const marked = rearrangementOf(b);
        const unavailability =
          b.status === "rejected"
            ? { kind: "rejected", reason: b.rejection_reason, alternative_suggestion: b.alternative_suggestion }
            : marked
              ? {
                  kind: "venue_unavailable",
                  reason: null,
                  alternative_suggestion: null,
                  block: {
                    id: marked.id,
                    starts_at: marked.starts_at,
                    ends_at: marked.ends_at,
                    reason: marked.reason,
                    note: marked.note,
                    ended_early_at: marked.ended_early_at ?? null,
                    scheduled_ends_at: marked.scheduled_ends_at ?? null,
                  },
                  flagged_at: "2026-11-02T01:00:00Z",
                }
              : isLive(b) && !active
                ? { kind: "venue_inactive", reason: null, alternative_suggestion: null }
                : null;
        const next_action = marked && b.restore_requested_at
          ? "venue_staff_to_restore"
          : unavailability
          ? "coordinator_to_rebook"
          : b.status === "requested"
            ? "venue_staff_to_decide"
            : b.status === "held"
              ? "coordinator_to_confirm"
              : "none";
        const replacement_booking_id = marked ? (liveReplacementOf(b)?.id ?? null) : null;
        return { ...b, unavailability, next_action, replacement_booking_id };
      });
    const live = db.bookings.filter((b) => b.event.id === event.id && isLive(b));
    const primary = live.find((b) => b.is_primary) ?? null;
    const allocated = live.reduce((sum, b) => sum + b.expected_attendees, 0);
    const expected = event.expected_attendees;
    return HttpResponse.json({
      bookings,
      venues_arranged:
        live.length > 0 &&
        live.every((b) => b.status === "approved" && !rearrangementOf(b)) &&
        live.filter((b) => b.is_primary).length === 1 &&
        (expected === null || allocated >= expected),
      primary_booking_id: primary?.id ?? null,
      allocated_attendees: allocated,
      expected_attendees: expected,
      next_action: live.length > 0 && !primary ? "choose_primary" : null,
    });
  }),

  // US25 (SCRUM-93), identified by X-User-Id. The expiry's rules (future, 14 days, before the start) and the
  // conflict check are the API's (backend/tests/venue/test_holds.py); this stores the hold and needs an expiry,
  // so a flow sees its own writes. Other refusals: server.use(...).
  // US23a (SCRUM-90): Venue staff mark a venue unavailable. The rules (AC 2's order, a period already over, the
  // reasons) are the API's (backend/tests/venue/test_unavailability.py); this marks the live bookings and holds
  // whose occupied window the period overlaps, so a flow sees its own writes.
  // US23b (SCRUM-91) AC 5 (D118): Venue staff end a period early.
  route("post", "/api/v1/venues/:venueId/blocks/:blockId/end", ({ request, params }) => {
    if (userRole(request) !== "venue_staff") return error(403, "FORBIDDEN");
    const block = db.blocks.find((b) => b.id === params.blockId && b.venue_id === params.venueId);
    const venue = db.venues.find((v) => v.id === params.venueId);
    if (!block || !venue) return error(404, "NOT_FOUND");
    if (block.ended_early_at) return error(409, "BLOCK_ENDED");
    const now = new Date().toISOString();
    block.scheduled_ends_at = block.ends_at;
    block.ends_at = now > block.starts_at ? now : block.starts_at;
    block.ended_early_at = now;
    const still = db.bookings.filter((b) => block.affects.includes(b.id) && rearrangementOf(b) === block);
    const { id, name, location, capacity } = venue;
    return HttpResponse.json({
      id: block.id,
      venue: { id, name, location, capacity },
      starts_at: block.starts_at,
      ends_at: block.ends_at,
      reason: block.reason,
      note: block.note,
      created_by_user_id: null,
      created_at: "2026-11-02T01:00:00Z",
      ended_early_at: block.ended_early_at,
      scheduled_ends_at: block.scheduled_ends_at,
      affected_bookings: still.map((b) => ({
        id: b.id, reference: b.reference, status: b.status, event: b.event, starts_at: b.starts_at, ends_at: b.ends_at,
      })),
      already_affected_bookings: [],
    });
  }),

  route("post", "/api/v1/venues/:venueId/blocks", ({ request, params, body }) => {
    if (userRole(request) !== "venue_staff") return error(403, "FORBIDDEN");
    const sent = (body ?? {}) as Record<string, unknown>;
    const missing = ["starts_at", "ends_at", "reason"].filter((field) => !sent[field]);
    if (missing.length > 0) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    const venue = db.venues.find((v) => v.id === params.venueId);
    if (!venue) return error(404, "NOT_FOUND");
    const startsAt = String(sent.starts_at);
    const endsAt = String(sent.ends_at);
    if (Date.parse(endsAt) <= Date.parse(startsAt)) {
      return error(422, "INVALID_BLOCK", { fields: ["ends_at"], errors: { ends_at: "The end must be after the start." } });
    }
    const overlapping = db.bookings
      .filter(
        (b) =>
          b.venue.id === venue.id &&
          (isLive(b) || b.status === "held") &&
          Date.parse(b.occupied_starts_at) < Date.parse(endsAt) &&
          Date.parse(startsAt) < Date.parse(b.occupied_ends_at),
      )
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at));
    // D115: one an earlier period marked keeps it; the response still lists it (Matt's #133 review).
    const affected = overlapping.filter((b) => !rearrangementOf(b));
    const already = overlapping.filter((b) => rearrangementOf(b));
    const summary = (b: VenueBooking) => ({
      id: b.id,
      reference: b.reference,
      status: b.status,
      event: b.event,
      starts_at: b.starts_at,
      ends_at: b.ends_at,
    });
    const block = seedBlock(venue, {
      starts_at: startsAt,
      ends_at: endsAt,
      reason: String(sent.reason),
      note: typeof sent.note === "string" ? sent.note : null,
      affects: affected.map((b) => b.id),
    });
    const { id, name, location, capacity } = venue;
    return HttpResponse.json(
      {
        id: block.id,
        venue: { id, name, location, capacity },
        starts_at: block.starts_at,
        ends_at: block.ends_at,
        reason: block.reason,
        note: block.note,
        created_by_user_id: request.headers.get("X-User-Id"),
        created_at: "2026-11-02T01:00:00Z",
        affected_bookings: affected.map(summary),
        already_affected_bookings: already.map(summary),
      },
      { status: 201 },
    );
  }),

  route("get", "/api/v1/venue-holds/events", ({ request }) => {
    if (userRole(request) !== "venue_staff") return error(403, "FORBIDDEN");
    const events = db.requests
      .filter((r) => r.status === "approved" || r.status === "planning")
      .map((r) => ({
        id: r.id,
        name: r.name,
        request_reference: r.request_reference,
        status: r.status,
        start_at: r.start_at ?? null,
        end_at: r.end_at ?? null,
        preferred_dates: r.preferred_dates,
        preferred_start_time: r.preferred_start_time,
        preferred_end_time: r.preferred_end_time,
        expected_attendees: r.expected_attendees,
      }));
    return HttpResponse.json({ events } as unknown as JsonBodyType);
  }),

  route("post", "/api/v1/venue-holds", ({ request, body }) => {
    if (userRole(request) !== "venue_staff") return error(403, "FORBIDDEN");
    const sent = (body ?? {}) as Record<string, unknown>;
    const missing = [...BOOKING_REQUIRED, "hold_expires_at"].filter(
      (field) => sent[field] === undefined || sent[field] === null || sent[field] === "",
    );
    if (missing.length > 0) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    const event = db.requests.find((r) => r.id === sent.event_id && (r.status === "approved" || r.status === "planning"));
    const venue = db.venues.find((v) => v.id === sent.venue_id && v.is_active);
    if (!event || !venue) return error(404, "NOT_FOUND");
    const staff = request.headers.get("X-User-Id")!;
    const booking = seedBooking(event, venue, {
      requested_by_user_id: staff,
      starts_at: String(sent.starts_at),
      ends_at: String(sent.ends_at),
      expected_attendees: Number(sent.expected_attendees),
      room_layout: String(sent.room_layout),
      purpose: String(sent.purpose).trim(),
      status: "held",
      is_primary: false,
      hold_expires_at: String(sent.hold_expires_at),
      held_by_user_id: staff,
    });
    return HttpResponse.json({ ...booking, warnings: [] }, { status: 201 });
  }),

  route("post", "/api/v1/venue-bookings/:id/confirm", ({ request, params }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const booking = db.bookings.find((b) => b.id === params.id);
    const event = booking && db.requests.find((r) => r.id === booking.event.id);
    if (!booking || !event || !assignedTo(event, request.headers.get("X-User-Id")!)) return error(404, "NOT_FOUND");
    if (booking.status !== "held") return error(409, "HOLD_NOT_HELD", { status: booking.status });
    // US23a: a hold the venue's unavailability overlaps can't be confirmed.
    if (rearrangementOf(booking)) {
      return error(409, "VENUE_UNAVAILABLE", {
        message: "This venue has become unavailable for part of the held time, so the hold can't be confirmed.",
      });
    }
    Object.assign(booking, {
      status: "requested",
      requested_by_user_id: request.headers.get("X-User-Id")!,
      is_primary: !db.bookings.some((b) => b.event.id === event.id && b.is_primary && isLive(b)),
    });
    return HttpResponse.json(booking);
  }),

  // US24 AC 4 (D68): the event's coordinator makes one of its live bookings the primary venue.
  // US23b (SCRUM-91) AC 5 (D118): the event's coordinator asks to restore a marked booking once its period ended
  // early; Venue staff list, confirm or decline. Whether every block over the whole occupied window is gone is the
  // API's check; here, only that the marking period was ended early.
  route("post", "/api/v1/venue-bookings/:id/restore", ({ request, params }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const booking = db.bookings.find((b) => b.id === params.id);
    const event = booking && db.requests.find((r) => r.id === booking.event.id);
    if (!booking || !event || !assignedTo(event, request.headers.get("X-User-Id")!)) return error(404, "NOT_FOUND");
    const marked = rearrangementOf(booking);
    if (!marked) return error(409, "BOOKING_NOT_REPLACEABLE", { status: booking.status, message: "This booking doesn't need rearrangement." });
    if (!marked.ended_early_at) return error(409, "VENUE_UNAVAILABLE", { conflict: { starts_at: marked.starts_at, ends_at: marked.ends_at } });
    if (booking.restore_requested_at) {
      return error(409, "RESTORE_ALREADY_REQUESTED", { message: "Venue staff are already asked to restore it." });
    }
    booking.restore_requested_at = "2026-11-03T01:00:00Z";
    booking.restore_requested_by_user_id = request.headers.get("X-User-Id");
    booking.restore_declined_at = null;
    booking.restore_decline_reason = null;
    return HttpResponse.json(booking);
  }),

  route("get", "/api/v1/venue-bookings/restore-requests", ({ request }) => {
    if (userRole(request) !== "venue_staff") return error(403, "FORBIDDEN");
    return HttpResponse.json({ bookings: db.bookings.filter((b) => b.restore_requested_at && rearrangementOf(b)) });
  }),

  route("post", "/api/v1/venue-bookings/:id/restore/:decision", ({ request, params, body }) => {
    if (userRole(request) !== "venue_staff") return error(403, "FORBIDDEN");
    const booking = db.bookings.find((b) => b.id === params.id);
    if (!booking) return error(404, "NOT_FOUND");
    const marked = rearrangementOf(booking);
    if (!marked || !booking.restore_requested_at) return error(409, "RESTORE_NOT_REQUESTED", { status: booking.status });
    if (params.decision === "confirm") marked.affects = marked.affects.filter((id) => id !== booking.id);
    booking.restore_requested_at = null;
    booking.restore_requested_by_user_id = null;
    // Matt's #134 review: a decline is kept, with any reason, until the coordinator asks again.
    const declined = params.decision === "decline";
    const reason = (body as { reason?: string } | null)?.reason;
    booking.restore_declined_at = declined ? "2026-11-03T02:00:00Z" : null;
    booking.restore_decline_reason = declined ? (reason ?? null) : null;
    return HttpResponse.json(booking);
  }),

  route("post", "/api/v1/venue-bookings/:id/make-primary", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const booking = db.bookings.find((b) => b.id === params.id);
    const event = booking && db.requests.find((r) => r.id === booking.event.id);
    if (!booking || !event || !assignedTo(event, request.headers.get("X-User-Id")!)) return error(404, "NOT_FOUND");
    if (!isLive(booking)) return error(409, "BOOKING_NOT_LIVE", { status: booking.status });
    db.bookings.filter((b) => b.event.id === event.id && isLive(b)).forEach((b) => (b.is_primary = false));
    booking.is_primary = true;
    return HttpResponse.json(booking);
  }),

  // US24 AC 7 (D73): Venue staff record an approved booking's preparation status.
  route("post", "/api/v1/venue-bookings/:id/preparation", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "venue_staff") return error(403, "FORBIDDEN");
    const value = (body as { preparation_status?: unknown } | null)?.preparation_status;
    if (value !== "not_started" && value !== "in_progress" && value !== "ready") {
      return error(422, "INVALID_BOOKING", {
        fields: ["preparation_status"],
        errors: { preparation_status: "Choose one of: not_started, in_progress, ready." },
      });
    }
    const booking = db.bookings.find((b) => b.id === params.id);
    if (!booking) return error(404, "NOT_FOUND");
    if (booking.status !== "approved") return error(409, "BOOKING_NOT_APPROVED", { status: booking.status });
    booking.preparation_status = value;
    return HttpResponse.json(booking);
  }),

  // Event requests (US1, US8), identified by X-User-Id.
  // US29a (SCRUM-97), identified by X-User-Id. Which fields a stage takes and each value's rules are the API's
  // (backend/tests/event/test_change_requests.py); this keeps the request Pending and the event unchanged, and
  // refuses a missing reason, so a flow sees its own writes. A test queues other refusals with server.use(...).
  route("post", "/api/v1/event-requests/:id/change-requests", ({ request, params, body }) => {
    if (userRole(request) !== "organiser") return error(403, "FORBIDDEN");
    const event = db.requests.find((r) => r.id === params.id && r.created_by_user_id === request.headers.get("X-User-Id"));
    if (!event || event.status === "draft") return error(404, "NOT_FOUND");
    if (["rejected", "cancelled", "completed"].includes(event.status)) return error(409, "CHANGE_NOT_ALLOWED", { status: event.status });
    const { changes = {}, reason } = (body ?? {}) as { changes?: Record<string, unknown>; reason?: string };
    if (!reason?.trim()) return error(422, "MISSING_REQUIRED_FIELD", { fields: ["reason"] });
    const current = event as unknown as Record<string, unknown>;
    const created: FakeChangeRequest = {
      id: newId("change-request"),
      event_id: event.id,
      event_name: event.name,
      request_reference: event.request_reference,
      status: "pending_approval",
      reason: reason.trim(),
      changes: Object.entries(changes).map(([field, new_value]) => ({ field, old_value: current[field] ?? null, new_value })),
      created_at: new Date(Date.UTC(2026, 9, 1, 1, db.nextId)).toISOString(),
      requested_by_user_id: event.created_by_user_id ?? ORGANISER_ID,
      decided_at: null,
      decided_by: null,
      rejection_reason: null,
    };
    db.changeRequests.unshift(created);
    return HttpResponse.json(created as unknown as JsonBodyType, { status: 201 });
  }),

  // US9 (SCRUM-12), identified by X-User-Id. Which statuses can be cancelled, the start time and the releases are
  // the API's (backend/tests/event/test_cancellations.py); this keeps one pending request per event, needs a reason
  // and moves the event to cancelled, so a flow sees its own writes. Other refusals: server.use(...).
  route("get", "/api/v1/event-requests/:id/cancellations", ({ request, params }) => {
    const role = userRole(request);
    const userId = request.headers.get("X-User-Id");
    const event = db.requests.find((r) => r.id === params.id);
    const reader = role === "organiser" ? event?.created_by_user_id === userId : event?.coordinator?.id === userId;
    if (!event || event.status === "draft" || !reader) return error(404, "NOT_FOUND");
    return HttpResponse.json({ cancellations: db.cancellations.filter((c) => c.event_id === event.id) } as unknown as JsonBodyType);
  }),

  route("post", "/api/v1/event-requests/:id/cancellation-requests", ({ request, params, body }) => {
    if (userRole(request) !== "organiser") return error(403, "FORBIDDEN");
    const event = db.requests.find((r) => r.id === params.id && r.created_by_user_id === request.headers.get("X-User-Id"));
    if (!event || event.status === "draft") return error(404, "NOT_FOUND");
    return startCancellation(event, body, false);
  }),

  route("post", "/api/v1/event-requests/:id/cancel", ({ request, params, body }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const event = db.requests.find((r) => r.id === params.id && r.coordinator?.id === request.headers.get("X-User-Id"));
    if (!event || event.status === "draft") return error(404, "NOT_FOUND");
    return startCancellation(event, body, true);
  }),

  route("post", "/api/v1/event-cancellations/:id/:verb", ({ request, params, body }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const record = db.cancellations.find((c) => c.id === params.id);
    const event = record && db.requests.find((r) => r.id === record.event_id);
    if (!record || !event || event.coordinator?.id !== request.headers.get("X-User-Id")) return error(404, "NOT_FOUND");
    const reason = ((body ?? {}) as { reason?: string }).reason?.trim();
    if (params.verb === "reject" && !reason) return error(422, "MISSING_REQUIRED_FIELD", { fields: ["reason"] });
    if (record.status !== "pending") return error(409, "CANCELLATION_NOT_PENDING", { status: record.status });
    record.status = params.verb === "approve" ? "approved" : "rejected";
    record.decided_by = { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name };
    record.decided_at = cancellationTime();
    record.rejection_reason = params.verb === "reject" ? reason! : null;
    if (params.verb === "approve") event.status = "cancelled";
    record.event_status = event.status;
    return HttpResponse.json(record as unknown as JsonBodyType);
  }),

  // US29b (SCRUM-143): the coordinator's change requests and their decisions, and the review flags (rules above).
  // acting_as (Calvin's #127 review): only what the user decides in that role; omitted, both.
  route("get", "/api/v1/change-requests", ({ request }) => {
    const userId = request.headers.get("X-User-Id") ?? "";
    const roles = new Set<string>([userRole(request) ?? "", ...(db.extraRoles[userId] ?? [])]);
    if (!roles.has("coordinator") && !roles.has("coordinator_lead")) return error(403, "FORBIDDEN");
    const url = new URL(request.url);
    const status = url.searchParams.get("status") ?? "pending_approval";
    const eventId = url.searchParams.get("event_id");
    const actingAs = url.searchParams.get("acting_as");
    const mine = db.changeRequests
      .filter((r) => {
        const event = db.requests.find((e) => e.id === r.event_id);
        if (event === undefined) return false;
        const asCoordinator = roles.has("coordinator") && decides("coordinator", userId, r, event);
        const asLead = roles.has("coordinator_lead") && decides("coordinator_lead", userId, r, event);
        return (actingAs !== "coordinator_lead" && asCoordinator) || (actingAs !== "coordinator" && asLead);
      })
      .filter((r) => !eventId || r.event_id === eventId)
      .filter((r) => status === "all" || (status === "decided" ? r.status !== "pending_approval" : r.status === "pending_approval"))
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    return HttpResponse.json({ change_requests: mine.map(changeView) } as unknown as JsonBodyType);
  }),

  route("get", "/api/v1/change-requests/:id", ({ request, params }) => {
    const found = decidableBy(request, params.id);
    return found instanceof Response ? found : HttpResponse.json(changeView(found) as unknown as JsonBodyType);
  }),

  route("post", "/api/v1/change-requests/:id/approve", ({ request, params }) => {
    const found = decidableBy(request, params.id);
    if (found instanceof Response) return found;
    if (found.status !== "pending_approval") return error(409, "CHANGE_REQUEST_NOT_PENDING", { status: found.status });
    const event = db.requests.find((r) => r.id === found.event_id)!;
    if (NOT_APPROVABLE.includes(event.status)) return error(409, "CHANGE_NOT_ALLOWED", { status: event.status });
    const current = event as unknown as Record<string, unknown>;
    const stale = found.changes.filter((c) => !sameValue(c.field, c.old_value, current[c.field]));
    if (stale.length > 0) {
      return error(409, "CHANGE_REQUEST_STALE", {
        fields: stale.map((c) => ({ field: c.field, reason: "changed", requested_from: c.old_value, current: current[c.field], proposed: c.new_value })) as JsonBodyType,
        message: "The event has changed since this request was made.",
      });
    }
    found.status = "approved";
    found.decided_at = DECIDED_AT;
    found.decided_by = deciderOf(request);
    const entries = found.changes.map((c) => historyEntry(found, "applied", c.field, current[c.field] ?? null, c.new_value));
    for (const c of found.changes) current[c.field] = c.new_value;
    entries.push(historyEntry(found, "decided", "change_request", "pending_approval", { decision: "approved" }));
    let statusChange: { from: string; to: string } | null = null;
    let safetyCleared = false;
    let flags: ReviewFlag[] = [];
    const significant = significantFields(found);
    if (significant.length > 0 && ARRANGED.includes(event.status)) {
      flags = raiseFlags(event, found, significant);
      if (event.status === "confirmed") {
        entries.push(historyEntry(found, "status_changed", "status", "confirmed", "planning"));
        entries.push(historyEntry(found, "confirmation_cleared", "confirmation", { confirmed_at: event.confirmed_at }, null));
        Object.assign(event, { status: "planning", confirmed_at: null });
        statusChange = { from: "confirmed", to: "planning" };
      }
      if (event.safety_approved_at) {
        entries.push(historyEntry(found, "safety_approval_cleared", "safety_approval", { approved_at: event.safety_approved_at }, null));
        event.safety_approved_at = null;
        safetyCleared = true;
      }
    }
    db.history[event.id] = [...entries.reverse(), ...(db.history[event.id] ?? [])];
    return HttpResponse.json({
      change_request: changeView(found),
      event,
      status_change: statusChange,
      flags,
      safety_review_required: safetyCleared,
    } as unknown as JsonBodyType);
  }),

  route("post", "/api/v1/change-requests/:id/reject", ({ request, params, body }) => {
    const found = decidableBy(request, params.id);
    if (found instanceof Response) return found;
    if (found.status !== "pending_approval") return error(409, "CHANGE_REQUEST_NOT_PENDING", { status: found.status });
    const reason = ((body ?? {}) as { reason?: unknown }).reason;
    const text = typeof reason === "string" ? reason.trim() : "";
    if (!text) return error(422, "MISSING_REQUIRED_FIELD", { fields: ["reason"] });
    if (text.length > 1000) return error(422, "INVALID_CHANGE_DECISION", { fields: ["reason"], errors: { reason: "Too long." } });
    const event = db.requests.find((r) => r.id === found.event_id)!;
    Object.assign(found, { status: "rejected", decided_at: DECIDED_AT, rejection_reason: text });
    found.decided_by = deciderOf(request);
    db.history[event.id] = [
      historyEntry(found, "decided", "change_request", "pending_approval", { decision: "rejected", reason: text }),
      ...(db.history[event.id] ?? []),
    ];
    return HttpResponse.json({
      change_request: changeView(found),
      event,
      status_change: null,
      flags: [],
      safety_review_required: false,
    } as unknown as JsonBodyType);
  }),

  route("get", "/api/v1/events/:eventId/review-flags", ({ request, params }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const event = db.requests.find((r) => r.id === params.eventId);
    if (!event || event.coordinator?.id !== request.headers.get("X-User-Id")) return error(404, "NOT_FOUND");
    return HttpResponse.json({ flags: flagsOf(event.id) } as unknown as JsonBodyType);
  }),

  route("post", "/api/v1/review-flags/:id/clear", ({ request, params, body }) => {
    if (userRole(request) !== "coordinator") return error(403, "FORBIDDEN");
    const flag = db.reviewFlags.find((f) => f.id === params.id);
    const event = flag && db.requests.find((r) => r.id === flag.event_id);
    if (!flag || !event || event.coordinator?.id !== request.headers.get("X-User-Id")) return error(404, "NOT_FOUND");
    if (flag.cleared_at) return error(409, "FLAG_ALREADY_CLEARED");
    const note = ((body ?? {}) as { note?: string | null }).note?.trim() || null;
    Object.assign(flag, { cleared_at: DECIDED_AT, cleared_by: { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name }, cleared_note: note, open: false });
    return HttpResponse.json(flag as unknown as JsonBodyType);
  }),

  route("get", "/api/v1/me/change-requests", ({ request }) => {
    if (userRole(request) !== "organiser") return error(403, "FORBIDDEN");
    const eventId = new URL(request.url).searchParams.get("event_id");
    const mine = db.changeRequests.filter((r) => !eventId || r.event_id === eventId);
    return HttpResponse.json({ change_requests: mine } as unknown as JsonBodyType);
  }),

  // US15 (SCRUM-140), identified by X-User-Id: the organiser's own request's agenda. The window (D94) is the API's
  // (backend/tests/agenda/test_event_sessions_api.py); this keeps the fields, the status rule (D93) and one track
  // (D95), so a flow sees its own writes in the API's order. A test queues other refusals with server.use(...).
  route("get", "/api/v1/event-requests/:id/sessions", ({ request, params }) => {
    const event = ownRequest(request, params.id);
    if (!event) return error(404, "NOT_FOUND");
    return HttpResponse.json({ sessions: agendaOf(event.id) } as unknown as JsonBodyType);
  }),

  route("post", "/api/v1/event-requests/:id/sessions", ({ request, params, body }) => {
    if (userRole(request) !== "organiser") return error(403, "FORBIDDEN");
    const event = ownRequest(request, params.id);
    if (!event) return error(404, "NOT_FOUND");
    if (!AGENDA_EDITABLE.includes(event.status)) return error(409, "AGENDA_NOT_EDITABLE", { status: event.status });
    const values = sessionValues({}, body);
    const refused = refuseSession(event.id, values);
    if (refused) return refused;
    const created: FakeSession = { id: newId("session"), event_id: event.id, outside_window: false, ...(values as Omit<FakeSession, "id" | "event_id" | "outside_window">) };
    db.sessions.push(created);
    return HttpResponse.json(created as unknown as JsonBodyType, { status: 201 });
  }),

  route("patch", "/api/v1/event-sessions/:id", ({ request, params, body }) => {
    if (userRole(request) !== "organiser") return error(403, "FORBIDDEN");
    const session = db.sessions.find((s) => s.id === params.id);
    const event = session && ownRequest(request, session.event_id);
    if (!session || !event) return error(404, "NOT_FOUND");
    if (!AGENDA_EDITABLE.includes(event.status)) return error(409, "AGENDA_NOT_EDITABLE", { status: event.status });
    const values = sessionValues(session, body);
    const refused = refuseSession(event.id, values, session.id);
    if (refused) return refused;
    Object.assign(session, values);
    return HttpResponse.json(session as unknown as JsonBodyType);
  }),

  route("delete", "/api/v1/event-sessions/:id", ({ request, params }) => {
    if (userRole(request) !== "organiser") return error(403, "FORBIDDEN");
    const session = db.sessions.find((s) => s.id === params.id);
    const event = session && ownRequest(request, session.event_id);
    if (!session || !event) return error(404, "NOT_FOUND");
    if (!AGENDA_EDITABLE.includes(event.status)) return error(409, "AGENDA_NOT_EDITABLE", { status: event.status });
    db.sessions = db.sessions.filter((s) => s.id !== session.id);
    return new HttpResponse(null, { status: 204 });
  }),

  route("get", "/api/v1/me/event-requests", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    const userId = request.headers.get("X-User-Id")!;
    const mine = db.requests.filter((r) => r.created_by_user_id === userId);
    return HttpResponse.json({ event_requests: [...mine].reverse() });
  }),

  // SCRUM-13: the Lead's queue, picker and assign. "unassigned" is registered before ":id".
  route("get", "/api/v1/event-requests/unassigned", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator_lead") return error(403, "FORBIDDEN");
    const queue = db.requests
      .filter((r) => r.status === "submitted" && r.coordinator === null)
      .map((r) => ({ ...r, organiser: r.created_by_user_id === ORGANISER_ID ? ORGANISER_PERSON : null }));
    return HttpResponse.json({ event_requests: queue });
  }),

  // SCRUM-86: the Lead's Assigned tab. In scope = the latest history record names the caller.
  route("get", "/api/v1/event-requests/assigned", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator_lead") return error(403, "FORBIDDEN");
    const caller = request.headers.get("X-User-Id");
    const url = new URL(request.url);
    const coordinator = url.searchParams.get("coordinator_id");
    const status = url.searchParams.get("status");
    const active = ["under_review", "awaiting_clarification", "approved", "planning", "confirmed", "preparation"];
    if (status && !active.includes(status)) return error(422, "INVALID_STATUS_FILTER", { status });
    const rows = db.requests
      .filter(
        (r) =>
          r.coordinator !== null &&
          active.includes(r.status) &&
          db.assignments[r.id]?.[0]?.assigned_by.id === caller &&
          (!coordinator || r.coordinator.id === coordinator) &&
          (!status || r.status === status),
      )
      .map((r) => ({ ...r, event_date: r.preferred_dates?.[0] ?? null }));
    return HttpResponse.json({ event_requests: rows });
  }),

  route("get", "/api/v1/coordinators", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator_lead") return error(403, "FORBIDDEN");
    const planning_count = db.requests.filter(
      (r) => r.coordinator?.id === COORDINATOR_PERSON.id && WORKLOAD_STATUSES.has(r.status),
    ).length;
    const others = db.otherCoordinators.map((person) => ({
      ...person,
      planning_count: db.requests.filter((r) => r.coordinator?.id === person.id && WORKLOAD_STATUSES.has(r.status)).length,
    }));
    return HttpResponse.json({ coordinators: [{ ...COORDINATOR_PERSON, planning_count }, ...others] });
  }),

  // SCRUM-83: the Lead moves an event to a different coordinator, with a reason.
  route("post", "/api/v1/event-requests/:id/reassignment", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator_lead") return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || found.status === "draft") return error(404, "NOT_FOUND");
    const active = ["under_review", "awaiting_clarification", "approved", "planning", "confirmed", "preparation"];
    if (found.coordinator === null || !active.includes(found.status)) {
      return error(409, "REASSIGNMENT_NOT_ALLOWED", { status: found.status });
    }
    const { coordinator_id: target, reason } = (body as { coordinator_id?: string; reason?: string } | null) ?? {};
    if (!reason?.trim()) return error(422, "MISSING_REQUIRED_FIELD", { fields: ["reason"] });
    if (target === found.coordinator.id) return error(422, "INVALID_COORDINATOR", { reason: "same_coordinator" });
    const people = [COORDINATOR_PERSON, ...db.otherCoordinators];
    const picked = people.find((person) => person.id === target);
    if (!picked) return error(422, "INVALID_COORDINATOR", { reason: target === LEAD_ID ? "self_assignment" : "not_a_coordinator" });
    found.coordinator = { id: picked.id, name: picked.name };
    db.assignments[found.id] = [
      {
        id: newId("assignment"),
        kind: "reassignment",
        assigned_by: LEAD_PERSON,
        coordinator: picked,
        reason: reason.trim(),
        created_at: "2026-10-27T03:15:00Z",
      },
      ...(db.assignments[found.id] ?? []),
    ];
    return HttpResponse.json(found);
  }),

  // SCRUM-83 AC 6 (screen: SCRUM-146): the event's coordinator asks the Leads to move it. Nothing moves here
  // either; the Events screen's events (US12) count as the caller's, as GET /events/{id} does.
  route("post", "/api/v1/event-requests/:id/transfer-request", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const userId = request.headers.get("X-User-Id")!;
    const found =
      db.requests.find((r) => r.id === params.id && r.status !== "draft" && assignedTo(r, userId)) ??
      db.coordinatedEvents.find((e) => e.id === params.id);
    if (!found) return error(404, "NOT_FOUND");
    const active = ["under_review", "awaiting_clarification", "approved", "planning", "confirmed", "preparation"];
    if (!active.includes(found.status)) return error(409, "REASSIGNMENT_NOT_ALLOWED", { status: found.status });
    const reason = (body as { reason?: string } | null)?.reason;
    if (!reason?.trim()) return error(422, "MISSING_REQUIRED_FIELD", { fields: ["reason"] });
    return HttpResponse.json({ status: "requested" }, { status: 202 });
  }),

  route("post", "/api/v1/event-requests/:id/assignment", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator_lead") return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || found.status === "draft") return error(404, "NOT_FOUND");
    if (found.status !== "submitted" || found.coordinator !== null) {
      return error(409, "ASSIGNMENT_NOT_ALLOWED", { status: found.status });
    }
    const target = (body as { coordinator_id?: string } | null)?.coordinator_id;
    if (target === LEAD_ID) return error(422, "INVALID_COORDINATOR", { reason: "self_assignment" });
    if (target !== COORDINATOR_PERSON.id) return error(422, "INVALID_COORDINATOR", { reason: "not_a_coordinator" });
    Object.assign(found, { status: "under_review", coordinator: { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name } });
    db.assignments[found.id] = [
      {
        id: newId("assignment"),
        kind: "assignment",
        assigned_by: LEAD_PERSON,
        coordinator: COORDINATOR_PERSON,
        created_at: "2026-10-24T03:15:00Z",
      },
      ...(db.assignments[found.id] ?? []),
    ];
    return HttpResponse.json(found);
  }),

  route("get", "/api/v1/event-requests/:id/assignment-history", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator_lead") return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || found.status === "draft") return error(404, "NOT_FOUND");
    return HttpResponse.json({ assignments: db.assignments[found.id] ?? [] });
  }),

  route("get", "/api/v1/event-requests", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator" && role !== "coordinator_lead") return error(403, "FORBIDDEN");
    const userId = request.headers.get("X-User-Id")!;
    // A Lead sees the whole queue; a coordinator only the requests assigned to them (D48).
    return HttpResponse.json({ event_requests: db.requests.filter((r) => r.status !== "draft" && visibleTo(r, role, userId)) });
  }),

  route("post", "/api/v1/event-requests", ({ request, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "organiser") return error(403, "FORBIDDEN");
    const created = seedRequest({ ...(body as EventRequestWrite), created_by_user_id: request.headers.get("X-User-Id") });
    return HttpResponse.json(created, { status: 201 });
  }),

  route("get", "/api/v1/event-requests/:id", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (!REQUEST_READERS.has(role)) return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || !readableBy(found, role, request.headers.get("X-User-Id")!)) return error(404, "NOT_FOUND");
    return HttpResponse.json(found);
  }),

  route("patch", "/api/v1/event-requests/:id", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || found.created_by_user_id !== request.headers.get("X-User-Id")) return error(404, "NOT_FOUND");
    if (found.status !== "draft") return error(409, "EVENT_REQUEST_LOCKED");
    Object.assign(found, body);
    return HttpResponse.json(found);
  }),

  route("post", "/api/v1/event-requests/:id/submit", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || found.created_by_user_id !== request.headers.get("X-User-Id")) return error(404, "NOT_FOUND");
    if (found.status !== "draft") return error(409, "EVENT_REQUEST_LOCKED");
    const missing = missingFields(found);
    if (missing.length > 0) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    Object.assign(found, {
      status: "submitted",
      preferred_dates: [...(found.preferred_dates ?? [])].sort(),
      request_reference: nextReference(),
      submitted_by_user_id: found.created_by_user_id,
      submitted_at: "2026-10-01T03:00:00Z",
    });
    return HttpResponse.json(found);
  }),

  route("get", "/api/v1/event-requests/:id/clarifications", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (!REQUEST_READERS.has(role)) return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || !visibleTo(found, role, request.headers.get("X-User-Id")!)) return error(404, "NOT_FOUND");
    const thread = db.clarifications
      .filter((m) => m.event_id === found.id)
      .sort((a, b) => a.round - b.round || (a.kind === "request" ? -1 : 1));
    return HttpResponse.json({ clarifications: thread });
  }),

  route("post", "/api/v1/event-requests/:id/clarifications", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    // Only the request's assigned coordinator asks (D48); anyone else's, or an unassigned one, is 404.
    if (!found || !visibleTo(found, role, request.headers.get("X-User-Id")!)) return error(404, "NOT_FOUND");
    const { sections = [], comment = "" } = (body ?? {}) as { sections?: string[]; comment?: string };
    const missing = [...(sections.length === 0 ? ["sections"] : []), ...(comment.trim() ? [] : ["comment"])];
    if (missing.length > 0) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    if (!CLARIFIABLE.has(found.status)) return error(409, "CLARIFICATION_NOT_ALLOWED", { status: found.status });
    const rounds = db.clarifications.filter((m) => m.event_id === found.id).map((m) => m.round);
    const clarification = seedClarification(found, {
      round: Math.max(0, ...rounds) + 1,
      sections: SECTION_ORDER.filter((key) => sections.includes(key)) as Clarification["sections"],
      comment: comment.trim(),
    });
    found.status = "awaiting_clarification";
    return HttpResponse.json({ clarification, status: found.status }, { status: 201 });
  }),

  route("post", "/api/v1/event-requests/:id/clarifications/response", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "organiser") return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || found.created_by_user_id !== request.headers.get("X-User-Id")) return error(404, "NOT_FOUND");
    const comment = ((body ?? {}) as { comment?: string }).comment ?? "";
    if (!comment.trim()) return error(422, "MISSING_REQUIRED_FIELD", { fields: ["comment"] });
    if (found.status !== "awaiting_clarification") return error(409, "NO_OPEN_CLARIFICATION", { status: found.status });
    const round = Math.max(...db.clarifications.filter((m) => m.event_id === found.id).map((m) => m.round));
    const clarification = seedClarification(found, { round, kind: "response", comment: comment.trim() });
    found.status = "under_review";
    return HttpResponse.json({ clarification, status: found.status }, { status: 201 });
  }),

  // US17 (SCRUM-84): the assigned coordinator decides a request under review, as
  // app/event/decision_service.py checks it: assigned (D48), not their own (D51), a reason to reject.
  ...(["approve", "reject"] as const).map((action) =>
    route("post", `/api/v1/event-requests/:id/${action}`, ({ request, params, body }) => {
      const role = userRole(request);
      if (!role) return error(401, "UNAUTHENTICATED");
      if (role !== "coordinator") return error(403, "FORBIDDEN");
      const userId = request.headers.get("X-User-Id")!;
      const found = db.requests.find((r) => r.id === params.id);
      if (!found || found.status === "draft" || !assignedTo(found, userId)) return error(404, "NOT_FOUND");
      if (found.created_by_user_id === userId) return error(403, "SELF_DECISION_NOT_ALLOWED");
      const reason = ((body ?? {}) as { reason?: string | null }).reason?.trim() ?? "";
      if (action === "reject" && !reason) return error(422, "MISSING_REQUIRED_FIELD", { fields: ["reason"] });
      if (found.status !== "under_review") return error(409, "REQUEST_NOT_DECIDABLE", { status: found.status });
      // Approving moves it to Planning with the earliest preferred date at the preferred times, Singapore time (D53, D123).
      const day = [...(found.preferred_dates ?? [])].sort()[0];
      const at = (clock: string | null | undefined) =>
        day && clock ? new Date(`${day}T${clock.slice(0, 5)}:00+08:00`).toISOString() : null;
      if (action === "approve") {
        found.start_at = found.start_at ?? at(found.preferred_start_time);
        found.end_at = found.end_at ?? at(found.preferred_end_time);
      }
      Object.assign(found, {
        status: action === "approve" ? "planning" : "rejected",
        decided_at: "2026-10-02T03:00:00Z",
        decided_by: found.coordinator,
        rejection_reason: action === "reject" ? reason : null,
      });
      return HttpResponse.json(found);
    }),
  ),

  // US18 (SCRUM-85): readiness, confirm and Preparation for the assigned coordinator, as
  // app/event/confirmation_service.py has them. Which arrangements count is the API's rule
  // (backend/tests/event/test_confirmation.py); here the same three checks over the fake's rows.
  route("get", "/api/v1/event-requests/:id/readiness", ({ request, params }) => {
    const found = confirmableBy(request, params.id as string);
    if (found instanceof Response) return found;
    if (!["approved", "planning", "confirmed", "preparation"].includes(found.status)) {
      return error(409, "CONFIRMATION_NOT_ALLOWED", { status: found.status });
    }
    return HttpResponse.json(readinessOf(found));
  }),

  route("post", "/api/v1/event-requests/:id/confirmation", ({ request, params }) => {
    const found = confirmableBy(request, params.id as string);
    if (found instanceof Response) return found;
    if (found.status !== "approved" && found.status !== "planning") {
      return error(409, "CONFIRMATION_NOT_ALLOWED", { status: found.status });
    }
    const readiness = readinessOf(found);
    if (!readiness.ready) {
      return error(409, "EVENT_NOT_READY", { outstanding: readiness.items.filter((i) => !i.complete), items: readiness.items });
    }
    Object.assign(found, { status: "confirmed", confirmed_at: "2026-10-03T03:00:00Z" });
    return HttpResponse.json(found);
  }),

  route("post", "/api/v1/event-requests/:id/preparation", ({ request, params }) => {
    const found = confirmableBy(request, params.id as string);
    if (found instanceof Response) return found;
    if (found.status !== "confirmed") return error(409, "PREPARATION_NOT_ALLOWED", { status: found.status });
    found.status = "preparation";
    return HttpResponse.json(found);
  }),

  // Event Status Management: an ended event in Preparation is marked Completed (confirmation_service.complete).
  route("post", "/api/v1/event-requests/:id/completion", ({ request, params }) => {
    const found = confirmableBy(request, params.id as string);
    if (found instanceof Response) return found;
    if (found.status !== "preparation") return error(409, "COMPLETION_NOT_ALLOWED", { status: found.status });
    if (!found.end_at || new Date(found.end_at).getTime() > Date.now()) {
      return error(409, "EVENT_NOT_ENDED", { ends_at: found.end_at ?? null });
    }
    found.status = "completed";
    return HttpResponse.json(found);
  }),

  // US30a (SCRUM-99): the Safety Officer's queue and review, and the outcome the Organiser and
  // Coordinator read, as app/safety/service.py has them. Which events are ready is readinessOf's.
  route("get", "/api/v1/safety-reviews", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "safety_officer") return error(403, "FORBIDDEN");
    const events = db.requests
      .filter((r) => REVIEWABLE.has(r.status) && !r.safety_approved_at && safetyStateOf(r) === "pending" && arrangementsReady(r))
      .map((r) => ({
        event_id: r.id,
        name: r.name,
        request_reference: r.request_reference,
        expected_attendees: r.expected_attendees,
        venues: db.bookings.filter((b) => b.event.id === r.id && b.status === "approved").map((b) => b.venue.name),
        starts_at: db.bookings.find((b) => b.event.id === r.id)?.starts_at ?? null,
        resent: reviewsOf(r).length > 0,
      }));
    return HttpResponse.json({ events });
  }),

  route("get", "/api/v1/safety-reviews/:id", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "safety_officer") return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || !["approved", "planning", "confirmed", "preparation"].includes(found.status)) return error(404, "NOT_FOUND");
    const state = safetyStateOf(found);
    if (reviewsOf(found).length === 0 && !(state === "pending" && arrangementsReady(found))) return error(404, "NOT_FOUND");
    return HttpResponse.json({
      event: {
        id: found.id,
        name: found.name,
        request_reference: found.request_reference,
        status: found.status,
        expected_attendees: found.expected_attendees,
        room_layout_preference: found.room_layout_preference,
        accessibility_needs: found.accessibility_needs,
        equipment_needs: found.equipment_needs,
      },
      state,
      venues: db.bookings
        .filter((b) => b.event.id === found.id && b.status === "approved")
        .map((b) => ({
          booking_reference: b.reference,
          venue_name: b.venue.name,
          location: b.venue.location,
          venue_capacity: b.venue.capacity,
          venue_facilities: [],
          venue_accessibility_features: [],
          venue_room_layouts: [],
          starts_at: b.starts_at,
          ends_at: b.ends_at,
          expected_attendees: b.expected_attendees,
          room_layout: b.room_layout,
          required_facilities: b.required_facilities,
          required_accessibility_features: b.required_accessibility_features,
          special_requirements: b.special_requirements,
        })),
      equipment: db.equipmentLines
        .filter((l) => l.event.id === found.id && l.status !== "rejected")
        .map((l) => ({ equipment_type: l.equipment_type.name, quantity: l.quantity, notes: l.notes })),
      checklist: SAFETY_CHECKLIST.map(([key, label]) => ({ key, label })),
      change_areas: SAFETY_CHANGE_AREAS.map(([key, label]) => ({ key, label })),
      history: reviewsOf(found),
    });
  }),

  route("post", "/api/v1/safety-reviews/:id", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "safety_officer") return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || found.status === "draft") return error(404, "NOT_FOUND");
    if (!REVIEWABLE.has(found.status)) return error(409, "SAFETY_REVIEW_NOT_ALLOWED", { reason: "status", status: found.status });
    const state = safetyStateOf(found);
    if (state === "approved") return error(409, "SAFETY_REVIEW_NOT_ALLOWED", { reason: "already_approved", status: found.status });
    if (state === "rejected" || state === "changes_requested") {
      return error(409, "SAFETY_REVIEW_NOT_ALLOWED", { reason: "awaiting_revision", status: found.status });
    }
    if (!arrangementsReady(found)) {
      return error(409, "SAFETY_REVIEW_NOT_ALLOWED", { reason: "arrangements_incomplete", status: found.status });
    }
    if (flagsOf(found.id).some((f) => f.open)) {
      return error(409, "SAFETY_REVIEW_NOT_ALLOWED", { reason: "review_flags_open", status: found.status });
    }
    const sent = (body ?? {}) as {
      outcome?: "approved" | "rejected" | "changes_requested";
      checklist?: Record<string, { result?: "satisfactory" | "issue"; comment?: string | null }>;
      comments?: string;
      internal_notes?: string;
      areas?: string[];
    };
    const comments = (sent.comments ?? "").trim();
    const missing: string[] = [];
    if (!sent.outcome) missing.push("outcome");
    for (const [key] of SAFETY_CHECKLIST) if (!sent.checklist?.[key]?.result) missing.push(`checklist.${key}`);
    if ((sent.outcome === "rejected" || sent.outcome === "changes_requested") && !comments) missing.push("comments");
    if (sent.outcome === "changes_requested" && !sent.areas?.length) missing.push("areas");
    if (missing.length > 0) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    const flagged = SAFETY_CHECKLIST.filter(([key]) => sent.checklist![key].result === "issue").map(([key]) => `checklist.${key}`);
    if (sent.outcome === "approved" && flagged.length > 0) return error(422, "CHECKLIST_HAS_ISSUES", { fields: flagged });
    const created_at = `2026-10-04T03:${String(db.safetyReviews.length).padStart(2, "0")}:00Z`;
    const review: FakeSafetyReview = {
      id: newId("safety-review"),
      event_id: found.id,
      outcome: sent.outcome!,
      checklist: Object.fromEntries(
        SAFETY_CHECKLIST.map(([key]) => [key, { result: sent.checklist![key].result!, comment: sent.checklist![key].comment?.trim() || null }]),
      ),
      comments: comments || null,
      internal_notes: sent.internal_notes?.trim() || null,
      areas: sent.outcome === "changes_requested" ? SAFETY_CHANGE_AREAS.map(([key]) => key).filter((key) => sent.areas!.includes(key)) : null,
      reviewer: { id: request.headers.get("X-User-Id")!, name: "Sam Safety" },
      created_at,
    };
    db.safetyReviews.push(review);
    db.safetyResent[found.id] = false;
    if (review.outcome === "approved") found.safety_approved_at = created_at;
    return HttpResponse.json(review, { status: 201 });
  }),

  // US31 (SCRUM-107): the caller's own notifications, newest first, as app/notification/router.py has them.
  route("get", "/api/v1/me/notifications", ({ request }) => {
    const user = request.headers.get("X-User-Id");
    if (!user || !userRole(request)) return error(401, "UNAUTHENTICATED");
    const mine = db.notifications.filter((n) => n.user_id === user).sort((a, b) => b.created_at.localeCompare(a.created_at));
    const url = new URL(request.url);
    const shown = url.searchParams.get("unread_only") === "true" ? mine.filter((n) => !n.read) : mine;
    const limit = Number(url.searchParams.get("limit") ?? 50);
    return HttpResponse.json({
      notifications: shown.slice(0, limit).map(({ user_id: _user, ...rest }) => rest),
      unread_count: mine.filter((n) => !n.read).length,
    });
  }),

  route("get", "/api/v1/me/notifications/unread-count", ({ request }) => {
    const user = request.headers.get("X-User-Id");
    if (!user || !userRole(request)) return error(401, "UNAUTHENTICATED");
    return HttpResponse.json({ unread_count: db.notifications.filter((n) => n.user_id === user && !n.read).length });
  }),

  route("post", "/api/v1/me/notifications/read-all", ({ request }) => {
    const user = request.headers.get("X-User-Id");
    if (!user || !userRole(request)) return error(401, "UNAUTHENTICATED");
    const unread = db.notifications.filter((n) => n.user_id === user && !n.read);
    for (const n of unread) n.read = true;
    return HttpResponse.json({ updated: unread.length, unread_count: 0 });
  }),

  route("post", "/api/v1/me/notifications/:id/read", ({ request, params }) => {
    const user = request.headers.get("X-User-Id");
    if (!user || !userRole(request)) return error(401, "UNAUTHENTICATED");
    const found = db.notifications.find((n) => n.id === params.id && n.user_id === user);
    if (!found) return error(404, "NOT_FOUND");
    found.read = true;
    const { user_id: _user, ...rest } = found;
    return HttpResponse.json(rest);
  }),

  route("get", "/api/v1/event-requests/:id/safety-reviews", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (!REQUEST_READERS.has(role)) return error(403, "FORBIDDEN");
    const found = db.requests.find((r) => r.id === params.id);
    if (!found || !visibleTo(found, role, request.headers.get("X-User-Id")!)) return error(404, "NOT_FOUND");
    return HttpResponse.json({ state: safetyStateOf(found), reviews: reviewsOf(found).map(publicReview) });
  }),

  route("post", "/api/v1/event-requests/:id/safety-review-request", ({ request, params }) => {
    const found = confirmableBy(request, params.id as string);
    if (found instanceof Response) return found;
    if (!REVIEWABLE.has(found.status)) return error(409, "SAFETY_REVIEW_NOT_ALLOWED", { reason: "status", status: found.status });
    if (!["rejected", "changes_requested"].includes(safetyStateOf(found))) {
      return error(409, "SAFETY_REVIEW_NOT_ALLOWED", { reason: "not_rejected", status: found.status });
    }
    db.safetyResent[found.id] = true;
    return HttpResponse.json({ state: safetyStateOf(found), reviews: reviewsOf(found).map(publicReview) });
  }),

  // US26 equipment (SCRUM-109, SCRUM-110). Identified by X-User-Id, like every role route.
  route("get", "/api/v1/equipment-types", ({ request }) => {
    if (!userRole(request)) return error(401, "UNAUTHENTICATED");
    const types = [...db.equipmentTypes].sort((a, b) => a.name.localeCompare(b.name));
    return HttpResponse.json({ equipment_types: types });
  }),

  route("get", "/api/v1/me/equipment-events", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const mine = db.equipmentEvents
      .filter((e) => e.coordinator_id === request.headers.get("X-User-Id") && EQUIPMENT_ELIGIBLE.has(e.status))
      .sort((a, b) => a.start_at.localeCompare(b.start_at))
      .map(({ id, name, start_at, status }) => ({ id, name, start_at, status }));
    return HttpResponse.json({ events: mine });
  }),

  route("get", "/api/v1/events/:id/equipment-lines", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const event = managedEquipmentEvent(request, params.id);
    if (!event) return error(404, "NOT_FOUND");
    const lines = db.equipmentLines
      .filter((l) => l.event.id === event.id)
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    return HttpResponse.json({ lines });
  }),

  route("post", "/api/v1/events/:id/equipment-lines", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const event = managedEquipmentEvent(request, params.id);
    if (!event) return error(404, "NOT_FOUND");
    if (!EQUIPMENT_ELIGIBLE.has(event.status)) return error(409, "EVENT_NOT_ELIGIBLE", { status: event.status });
    // Both checked fields count as sent, so a missing one is named like an invalid one.
    const values: Record<string, unknown> = { equipment_type_id: undefined, quantity: undefined, ...(body as Record<string, unknown>) };
    const refused = invalidLine(values) ?? duplicateLine(event.id, values.equipment_type_id);
    if (refused) return refused;
    const line = seedEquipmentLine(event, db.equipmentTypes.find((t) => t.id === values.equipment_type_id)!, {
      quantity: values.quantity as number,
      notes: cleanNotes(values.notes),
      requested_by_user_id: request.headers.get("X-User-Id")!,
    });
    return HttpResponse.json(line, { status: 201 });
  }),

  route("patch", "/api/v1/equipment-lines/:id", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const line = db.equipmentLines.find((l) => l.id === params.id);
    if (!line || !managedEquipmentEvent(request, line.event.id)) return error(404, "NOT_FOUND");
    if (line.status !== "pending") return error(409, "LINE_NOT_PENDING", { status: line.status });
    const values = (body ?? {}) as Record<string, unknown>;
    const refused =
      invalidLine(values) ?? ("equipment_type_id" in values ? duplicateLine(line.event.id, values.equipment_type_id, line.id) : null);
    if (refused) return refused;
    // D64 (SCRUM-125): a recorded check no longer applies once the type or quantity changes.
    const changesCheck =
      ("equipment_type_id" in values && values.equipment_type_id !== line.equipment_type.id) ||
      ("quantity" in values && values.quantity !== line.quantity);
    if (changesCheck) line.availability_check = null;
    if ("equipment_type_id" in values) line.equipment_type = db.equipmentTypes.find((t) => t.id === values.equipment_type_id)!;
    if ("quantity" in values) line.quantity = values.quantity as number;
    if ("notes" in values) line.notes = cleanNotes(values.notes);
    // The real column is onupdate=now(); a fixed later stamp is enough to tell an edited line apart.
    line.updated_at = "2026-10-03T02:00:00Z";
    return HttpResponse.json(line);
  }),

  route("delete", "/api/v1/equipment-lines/:id", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const line = db.equipmentLines.find((l) => l.id === params.id);
    if (!line || !managedEquipmentEvent(request, line.event.id)) return error(404, "NOT_FOUND");
    if (line.status !== "pending") return error(409, "LINE_NOT_PENDING", { status: line.status });
    db.equipmentLines = db.equipmentLines.filter((l) => l.id !== line.id);
    return new HttpResponse(null, { status: 204 });
  }),

  route("get", "/api/v1/equipment-lines", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "tech_support") return error(403, "FORBIDDEN");
    // Pending lines to review (US26), or approved ones to reserve (US27, SCRUM-131).
    const status = new URL(request.url).searchParams.get("status") ?? "pending";
    const listed = db.equipmentLines
      .filter((l) => l.status === status)
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    return HttpResponse.json({ lines: listed });
  }),

  // US27 (SCRUM-131): the approved line's full quantity, or nothing; no fields.
  route("post", "/api/v1/equipment-lines/:id/reservation", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "tech_support") return error(403, "FORBIDDEN");
    const line = db.equipmentLines.find((l) => l.id === params.id);
    if (!line) return error(404, "NOT_FOUND");
    if (line.status !== "approved") return error(409, "LINE_NOT_APPROVED", { status: line.status });
    if (line.reservation) return error(409, "ALREADY_RESERVED");
    const short = db.reservationShortfalls[line.id];
    if (short) return error(409, "INSUFFICIENT_EQUIPMENT", { ...short });
    line.reservation = {
      quantity: line.quantity,
      reserved_by_user_id: request.headers.get("X-User-Id")!,
      reserved_at: "2026-10-02T04:00:00Z",
      released_because_event_cancelled: false,
    };
    return HttpResponse.json(line, { status: 201 });
  }),

  // US27 AC 5: releasing deletes the reservation (D74).
  route("delete", "/api/v1/equipment-lines/:id/reservation", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "tech_support") return error(403, "FORBIDDEN");
    const line = db.equipmentLines.find((l) => l.id === params.id);
    if (!line) return error(404, "NOT_FOUND");
    if (!line.reservation) return error(409, "NOT_RESERVED");
    line.reservation = null;
    return new HttpResponse(null, { status: 204 });
  }),

  // US14 (SCRUM-134): the event's coordinator only. Overlaps (STAFF_UNAVAILABLE) and EVENT_STARTED are
  // the API's to decide; tests that need them answer with server.use.
  route("get", "/api/v1/events/:id/tech-staff", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const event = managedEquipmentEvent(request, params.id);
    if (!event) return error(404, "NOT_FOUND");
    return HttpResponse.json(techStaffBody(event));
  }),

  route("post", "/api/v1/events/:id/tech-staff", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const event = managedEquipmentEvent(request, params.id);
    if (!event) return error(404, "NOT_FOUND");
    const ids = (body as { staff_user_ids?: unknown } | null)?.staff_user_ids;
    if (!Array.isArray(ids) || ids.length === 0) return HttpResponse.json({ detail: "staff_user_ids" }, { status: 422 });
    if (!techStaffBody(event).eligible) return error(409, "NO_APPROVED_TECH_REQUEST");
    const invalid = ids.filter((id) => !db.techStaff.some((p) => p.id === id));
    if (invalid.length) return error(422, "INVALID_STAFF", { staff_user_ids: invalid });
    const active = db.techStaffRows.filter((row) => row.event_id === event.id && !row.unassigned_at);
    const already = ids.filter((id) => active.some((row) => row.staff.id === id));
    if (already.length) return error(409, "ALREADY_ASSIGNED", { staff_user_ids: already });
    for (const id of ids) seedTechStaffAssignment(event, db.techStaff.find((p) => p.id === id)!);
    return HttpResponse.json(techStaffBody(event), { status: 201 });
  }),

  route("delete", "/api/v1/events/:id/tech-staff/:staffId", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const event = managedEquipmentEvent(request, params.id);
    if (!event) return error(404, "NOT_FOUND");
    const row = db.techStaffRows.find((r) => r.event_id === event.id && r.staff.id === params.staffId && !r.unassigned_at);
    if (!row) return error(409, "NOT_ASSIGNED");
    row.unassigned_at = techStaffStamp();
    row.unassigned_by = COORDINATOR_PERSON;
    return new HttpResponse(null, { status: 204 });
  }),

  // US5 (SCRUM-125): records the latest check on the line (D64), which updates the line like any change.
  route("post", "/api/v1/equipment-lines/:id/availability-check", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "tech_support") return error(403, "FORBIDDEN");
    const line = db.equipmentLines.find((l) => l.id === params.id);
    if (!line) return error(404, "NOT_FOUND");
    const found = db.availability[line.id] ?? setAvailability(line);
    const recorded = {
      sufficient: found.sufficient,
      shortfall: found.shortfall,
      checked_by_user_id: request.headers.get("X-User-Id")!,
      checked_at: "2026-10-02T03:00:00Z",
    };
    Object.assign(line, { availability_check: recorded, updated_at: recorded.checked_at });
    return HttpResponse.json({ ...found, ...recorded });
  }),

  route("post", "/api/v1/equipment-lines/:id/review", ({ request, params, body }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "tech_support") return error(403, "FORBIDDEN");
    const line = db.equipmentLines.find((l) => l.id === params.id);
    if (!line) return error(404, "NOT_FOUND");
    // D51 (SCRUM-120): not a line they requested, nor one for an event they coordinate.
    const userId = request.headers.get("X-User-Id");
    const lineEvent = db.equipmentEvents.find((e) => e.id === line.event.id);
    if (line.requested_by_user_id === userId || lineEvent?.coordinator_id === userId) {
      return error(403, "SELF_DECISION_NOT_ALLOWED");
    }
    const { decision, note, ...rest } = (body ?? {}) as Record<string, unknown>;
    // Unknown fields (a quantity, AC 6) and other decisions are FastAPI's generic 422.
    if ((decision !== "approved" && decision !== "rejected") || Object.keys(rest).length > 0) {
      return HttpResponse.json({ detail: "validation error" }, { status: 422 });
    }
    if (line.status !== "pending") return error(409, "LINE_NOT_PENDING", { status: line.status });
    Object.assign(line, {
      status: decision,
      review_note: cleanNotes(note),
      reviewed_by_user_id: TECH_SUPPORT_ID,
      reviewed_at: "2026-10-02T02:00:00Z",
    });
    return HttpResponse.json(line);
  }),

  // SCRUM-103/106: the first login after confirming creates the profile; Organiser or Attendee only.
  route("post", "/api/v1/auth/profile", ({ body }) => {
    const { full_name, role } = (body ?? {}) as { full_name?: string; role?: string };
    const missing = [["full_name", full_name], ["role", role]].filter(([, value]) => !value?.trim()).map(([name]) => name);
    if (missing.length) return error(422, "MISSING_REQUIRED_FIELD", { fields: missing });
    if (role !== "organiser" && role !== "attendee") return error(422, "INVALID_ROLE");
    return HttpResponse.json({ id: "new-user-id", email: "pat@example.com", full_name, role }, { status: 201 });
  }),
];

export const server = setupServer(...handlers);

/** Call at the top of an integration test file: starts the fake backend and resets it per test. */
export function startMockBackend() {
  beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
  afterEach(() => {
    server.resetHandlers();
    db = emptyDb();
  });
  afterAll(() => server.close());
}
