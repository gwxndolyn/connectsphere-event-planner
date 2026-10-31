import { http, HttpResponse, type JsonBodyType } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll } from "vitest";
import type { EventRegistrations } from "../features/eventRegistrations/types";
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
  status: "confirmed" | "waitlisted" | "offered";
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

// US2's venue closures, which the US21 calendar shows as "Unavailable" (SCRUM-123).
export interface FakeVenueBlock {
  id: string;
  venue_id: string;
  starts_at: string;
  ends_at: string;
  note: string | null;
}

export interface RecordedCall {
  method: string;
  path: string;
  url: URL;
  headers: Headers;
  body: unknown;
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
  // US28: the events each managing role sees, and what each event's registrations call returns.
  managedEvents: Record<"organiser" | "coordinator", EventRegistrations[]>;
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
    bookings: [],
    blocks: [],
    evaluations: {},
    equipmentTypes: [],
    equipmentEvents: [],
    equipmentLines: [],
    availability: {},
    reservationShortfalls: {},
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
  return db.registrations.filter((r) => r.event_id === event.id && r.status !== "waitlisted").length;
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
  return db.registrations.find((r) => r.event_id === eventId && r.attendee_id === attendeeId);
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

// Who may open a request and its thread at all (SCRUM-120, D54): other roles get 403.
const REQUEST_READERS = new Set(["organiser", "coordinator", "coordinator_lead"]);

// SCRUM-13: who the Lead can pick, as GET /api/v1/coordinators returns them.
export const COORDINATOR_PERSON = { id: COORDINATOR_ID, name: "Casey Tan", email: "casey.tan@smu.edu.sg" };
// SCRUM-67, D30: the statuses a coordinator is actively working an event through.
const WORKLOAD_STATUSES = new Set(["under_review", "awaiting_clarification", "approved", "planning"]);
export const LEAD_PERSON = { id: LEAD_ID, name: "Lena Lead", email: "lena.lead@smu.edu.sg" };
const ORGANISER_PERSON = { id: ORGANISER_ID, name: "Olivia Organiser", email: "event.organiser@smu.edu.sg" };

const CLARIFIABLE = new Set(["submitted", "under_review"]);

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

function cleanNotes(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

// US24 (SCRUM-128): a purpose too (D66).
// US24 (D71): the Organiser reads an event's venues once its request is approved.
const ORGANISER_VISIBLE = ["approved", "planning", "confirmed", "cancelled", "completed"];

function isLive(booking: VenueBooking): boolean {
  return booking.status === "requested" || booking.status === "approved";
}

const BOOKING_REQUIRED = ["event_id", "venue_id", "starts_at", "ends_at", "expected_attendees", "room_layout", "purpose"];
const SECTION_ORDER = ["details", "schedule", "attendance", "layout", "accessibility", "equipment", "registration"];

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

  // Body-only, no identity header (D7); linked to the attendee when the email is theirs (D3).
  route("post", "/api/v1/events/:eventId/waitlist", ({ params, body }) => {
    const event = db.events.find((e) => e.id === params.eventId);
    if (!event) return error(404, "NOT_FOUND");
    const email = (body as { email?: string } | null)?.email ?? "";
    if (db.registrations.some((r) => r.event_id === event.id && r.email === email)) {
      return error(409, "ALREADY_REGISTERED");
    }
    if (!event.waitlist_enabled) return error(409, "WAITLIST_NOT_ENABLED");
    if (seatsRemaining(event) > 0) return error(409, "SEATS_AVAILABLE");
    const registration = seedRegistration(event, {
      attendee_id: email === ATTENDEE_EMAIL ? ATTENDEE_ID : null,
      email,
      status: "waitlisted",
    });
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
      .filter((b) => b.venue.id === venue.id && live(b) && overlaps(b.occupied_starts_at, b.occupied_ends_at))
      .map((b) => ({
        kind: "booking",
        label: "Booking",
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
        },
        note: null,
      }));
    const blocks = db.blocks
      .filter((block) => block.venue_id === venue.id && overlaps(block.starts_at, block.ends_at))
      .map((block) => ({
        kind: "block",
        label: "Unavailable",
        starts_at: block.starts_at,
        ends_at: block.ends_at,
        occupied: { starts_at: block.starts_at, ends_at: block.ends_at },
        booking: null,
        note: block.note,
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
    const booking = seedBooking(event, venue, {
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
    if (!booking || booking.requested_by_user_id !== request.headers.get("X-User-Id")) return error(404, "NOT_FOUND");
    // US24 (D69): an approved booking can be withdrawn too, so the refusal says it isn't live.
    if (booking.status !== "requested" && booking.status !== "approved") {
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
    const pending = db.bookings.filter((b) => b.status === "requested").sort((a, b) => a.created_at.localeCompare(b.created_at));
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
        const unavailability =
          b.status === "rejected"
            ? { kind: "rejected", reason: b.rejection_reason, alternative_suggestion: b.alternative_suggestion }
            : isLive(b) && !active
              ? { kind: "venue_inactive", reason: null, alternative_suggestion: null }
              : null;
        const next_action = unavailability ? "coordinator_to_rebook" : b.status === "requested" ? "venue_staff_to_decide" : "none";
        return { ...b, unavailability, next_action };
      });
    const live = db.bookings.filter((b) => b.event.id === event.id && isLive(b));
    const primary = live.find((b) => b.is_primary) ?? null;
    const allocated = live.reduce((sum, b) => sum + b.expected_attendees, 0);
    const expected = event.expected_attendees;
    return HttpResponse.json({
      bookings,
      venues_arranged:
        live.length > 0 &&
        live.every((b) => b.status === "approved") &&
        live.filter((b) => b.is_primary).length === 1 &&
        (expected === null || allocated >= expected),
      primary_booking_id: primary?.id ?? null,
      allocated_attendees: allocated,
      expected_attendees: expected,
      next_action: live.length > 0 && !primary ? "choose_primary" : null,
    });
  }),

  // US24 AC 4 (D68): the event's coordinator makes one of its live bookings the primary venue.
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
    const active = ["under_review", "awaiting_clarification", "approved", "planning", "confirmed"];
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
    const active = ["under_review", "awaiting_clarification", "approved", "planning", "confirmed"];
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
    if (!found || !visibleTo(found, role, request.headers.get("X-User-Id")!)) return error(404, "NOT_FOUND");
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
      Object.assign(found, {
        status: action === "approve" ? "approved" : "rejected",
        decided_at: "2026-10-02T03:00:00Z",
        decided_by: found.coordinator,
        rejection_reason: action === "reject" ? reason : null,
      });
      return HttpResponse.json(found);
    }),
  ),

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
