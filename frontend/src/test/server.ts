import { http, HttpResponse, type JsonBodyType } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll } from "vitest";
import type { Clarification, EventRequest, EventRequestWrite } from "../features/eventRequest/types";
import type { VenueBooking } from "../features/venue/bookingTypes";
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
export const VENUE_STAFF_ID = "venue-staff-id";
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
  clarifications: Clarification[];
  // US22 venue bookings (SCRUM-113).
  bookings: VenueBooking[];
  calls: RecordedCall[];
  nextId: number;
  nextReference: number;
}

function emptyDb(): Db {
  return {
    venues: [],
    searchResult: [],
    events: [],
    registrations: [],
    requests: [],
    clarifications: [],
    bookings: [],
    calls: [],
    nextId: 1,
    nextReference: 1,
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

/** A US22 booking of `venue` for an event request (an approved one, in the screens' flows). */
export function seedBooking(request: EventRequest, venue: Venue, overrides: Partial<VenueBooking> = {}): VenueBooking {
  const booking: VenueBooking = {
    id: newId("booking"),
    event: { id: request.id, name: request.name, request_reference: request.request_reference, status: request.status },
    venue: { id: venue.id, name: venue.name, location: venue.location, capacity: venue.capacity },
    requested_by_user_id: COORDINATOR_ID,
    // Singapore 10:00–12:00 on 20 Nov 2026.
    starts_at: "2026-11-20T02:00:00Z",
    ends_at: "2026-11-20T04:00:00Z",
    expected_attendees: 30,
    room_layout: "classroom",
    required_facilities: [],
    required_accessibility_features: [],
    special_requirements: null,
    status: "requested",
    created_at: "2026-10-01T02:00:00Z",
    updated_at: "2026-10-01T02:00:00Z",
    withdrawn_at: null,
    ...overrides,
  };
  db.bookings.push(booking);
  return booking;
}

/** The venues the next search returns, in that order: the API decides which venues fit, not the fake. */
export function nextSearchResult(venues: Venue[]) {
  db.searchResult = venues;
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

const ROLES: Record<string, "organiser" | "coordinator" | "operations_manager"> = {
  [ORGANISER_ID]: "organiser",
  [COORDINATOR_ID]: "coordinator",
  // Venue staff is operations_manager until US16b (D19).
  [VENUE_STAFF_ID]: "operations_manager",
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

// D11: owner always; coordinators once it's past draft.
function visibleTo(request: EventRequest, role: string, userId: string) {
  if (role !== "organiser") return request.status !== "draft";
  return request.created_by_user_id === userId;
}

const CLARIFIABLE = new Set(["submitted", "under_review"]);
const BOOKING_REQUIRED = ["event_id", "venue_id", "starts_at", "ends_at", "expected_attendees", "room_layout"];
const SECTION_ORDER = ["details", "schedule", "attendance", "layout", "accessibility", "equipment", "registration"];

// --- Handlers -------------------------------------------------------------------------------

type Resolver = (args: { request: Request; params: Record<string, string>; body: unknown }) =>
  | Response
  | Promise<Response>;

function route(method: "get" | "post" | "patch", path: string, resolver: Resolver) {
  return http[method](`${API}${path}`, async ({ request, params }) => {
    const body: unknown = method === "get" ? null : await request.clone().json().catch(() => null);
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
      .filter((venue) => role === "operations_manager" || venue.is_active)
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
    const event = db.requests.find((r) => r.id === sent.event_id && r.status !== "draft");
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
    });
    return HttpResponse.json({ ...booking, warnings: [] }, { status: 201 });
  }),

  route("post", "/api/v1/venue-bookings/:id/withdraw", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    const booking = db.bookings.find((b) => b.id === params.id);
    if (!booking || booking.requested_by_user_id !== request.headers.get("X-User-Id")) return error(404, "NOT_FOUND");
    if (booking.status !== "requested") return error(409, "BOOKING_NOT_PENDING", { status: booking.status });
    Object.assign(booking, { status: "withdrawn", withdrawn_at: "2026-10-01T03:00:00Z", updated_at: "2026-10-01T03:00:00Z" });
    return HttpResponse.json(booking);
  }),

  route("get", "/api/v1/venue-bookings/pending", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "operations_manager") return error(403, "FORBIDDEN");
    const pending = db.bookings.filter((b) => b.status === "requested").sort((a, b) => a.created_at.localeCompare(b.created_at));
    return HttpResponse.json({ bookings: pending });
  }),

  route("get", "/api/v1/events/:id/venue-bookings", ({ request, params }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role === "organiser") return error(403, "FORBIDDEN");
    const event = db.requests.find((r) => r.id === params.id && r.status !== "draft");
    if (!event) return error(404, "NOT_FOUND");
    const bookings = db.bookings.filter((b) => b.event.id === event.id).sort((a, b) => a.starts_at.localeCompare(b.starts_at));
    return HttpResponse.json({ bookings });
  }),

  // Event requests (US1, US8), identified by X-User-Id.
  route("get", "/api/v1/me/event-requests", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    const userId = request.headers.get("X-User-Id")!;
    const mine = db.requests.filter((r) => r.created_by_user_id === userId);
    return HttpResponse.json({ event_requests: [...mine].reverse() });
  }),

  route("get", "/api/v1/event-requests", ({ request }) => {
    const role = userRole(request);
    if (!role) return error(401, "UNAUTHENTICATED");
    if (role !== "coordinator") return error(403, "FORBIDDEN");
    return HttpResponse.json({ event_requests: db.requests.filter((r) => r.status !== "draft") });
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
    if (!found || found.status === "draft") return error(404, "NOT_FOUND");
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
