import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { bookingReference, registrationApi, registrationErrorMessage } from "./api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

describe("bookingReference", () => {
  it("is the first 8 hex characters of the registration id, uppercased (deviation 17)", () => {
    expect(bookingReference("3f2a9c1e-7b44-4d2a-9e10-55aa00bb11cc")).toBe("3F2A9C1E");
  });

  it("skips the hyphens", () => {
    expect(bookingReference("abc-def12-3456")).toBe("ABCDEF12");
  });
});

describe("registrationErrorMessage", () => {
  it.each([
    ["EVENT_FULL", "This event filled up before your registration went through."],
    ["ALREADY_REGISTERED", "You're already registered for this event."],
    ["WAITLIST_NOT_ENABLED", "This event doesn't have a waitlist."],
    ["SEATS_AVAILABLE", "A seat is free now — you can register instead."],
    ["REGISTRATION_CLOSED", "Registration for this event isn't open right now."],
    ["REGISTRATION_NOT_ENABLED", "This event isn't taking registrations."],
    ["NOT_FOUND", "We couldn't find that event or registration. It may have been removed."],
    ["EVENT_STARTED", "This event has already started, so you can't withdraw."],
    ["NO_ACTIVE_OFFER", "This place is no longer being offered to you."],
    ["OFFER_EXPIRED", "This offer has expired, so the place has moved on."],
    ["ALREADY_WITHDRAWN", "This registration is no longer active."],
    ["REGISTRATION_NOT_ACTIVE", "This registration is no longer active."],
  ])("explains %s", (code, message) => {
    expect(registrationErrorMessage(new ApiError(409, code))).toBe(message);
  });

  it("names missing fields by their labels, falling back to the key", () => {
    const error = new ApiError(422, "MISSING_REQUIRED_FIELD", ["dietary", "tshirt"]);
    expect(registrationErrorMessage(error, { dietary: "Dietary requirements" })).toBe(
      "Please answer: Dietary requirements, tshirt.",
    );
  });

  it("points at VITE_DEV_ATTENDEE_ID when the attendee is unknown", () => {
    expect(registrationErrorMessage(new ApiError(401, "UNAUTHENTICATED"))).toContain("VITE_DEV_ATTENDEE_ID");
  });

  it("falls back for unknown codes and non-API errors", () => {
    const fallback = "The request could not be completed. Check the backend connection and try again.";
    expect(registrationErrorMessage(new ApiError(500, "HTTP_ERROR"))).toBe(fallback);
    expect(registrationErrorMessage(new TypeError("Failed to fetch"))).toBe(fallback);
  });
});

describe("registrationApi mapping", () => {
  it("maps GET /events/available to the board's shape", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        events: [
          {
            id: "e1",
            name: "Intro to Supabase: Live Coding",
            start_at: "2026-10-12T14:00:00+08:00",
            end_at: "2026-10-12T16:00:00+08:00",
            delivery_mode: "online",
            venue_name: null,
            join_link: "https://zoom.example/j/1",
            capacity: 200,
            seats_remaining: 199,
            is_full: false,
            waitlist_available: false,
            already_registered: true,
            registration_fields: [
              { field_key: "dietary", label: "Dietary requirements", field_type: "text", options: null, required: false },
            ],
          },
        ],
      }),
    );

    const [event] = await registrationApi.listAvailable();

    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/api/v1/events/available");
    expect(event).toEqual({
      id: "e1",
      title: "Intro to Supabase: Live Coding",
      format: "online",
      startsAt: "2026-10-12T14:00:00+08:00",
      endsAt: "2026-10-12T16:00:00+08:00",
      venue: undefined,
      joinUrl: "https://zoom.example/j/1",
      capacity: 200,
      seatsRemaining: 199,
      isFull: false,
      waitlistAvailable: false,
      alreadyRegistered: true,
      registrationFields: [
        { key: "dietary", label: "Dietary requirements", type: "text", options: null, required: false },
      ],
    });
  });

  it("maps GET /me/registrations into its three sections, tagging each row's status", async () => {
    const row = {
      registration_id: "r1",
      event_id: "e1",
      event_name: "Design Sprint Bootcamp",
      date: "2026-10-06",
      start_time: "10:00",
      end_time: "12:00",
      venue_name: "SMU Connexion",
      joining_info: "Studio 3-2",
      delivery_mode: "in_person",
    };
    fetchMock.mockResolvedValue(
      jsonResponse({
        confirmed: [row],
        waitlisted: [{ ...row, registration_id: "r2", waitlist_position: 3 }],
        offered: [{ ...row, registration_id: "r3", offer_expires_at: "2026-10-03T01:00:00Z" }],
      }),
    );

    const mine = await registrationApi.listMine();

    expect(mine.confirmed[0]).toMatchObject({
      id: "r1",
      eventId: "e1",
      status: "confirmed",
      eventTitle: "Design Sprint Bootcamp",
      format: "in-person",
      venue: "SMU Connexion",
      joiningInfo: "Studio 3-2",
    });
    expect(mine.waitlisted[0]).toMatchObject({ id: "r2", status: "waitlisted", waitlistPosition: 3 });
    expect(mine.offered[0]).toMatchObject({ id: "r3", status: "offered", offerExpiresAt: "2026-10-03T01:00:00Z" });
  });

  it("treats a missing offered section as empty", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ confirmed: [], waitlisted: [] }));
    await expect(registrationApi.listMine()).resolves.toEqual({ confirmed: [], waitlisted: [], offered: [] });
  });

  it("registers with the answers and maps the confirmation", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          registration_id: "r1",
          status: "confirmed",
          event: {
            name: "Tech Talk",
            start_at: "2026-10-02T14:00:00+08:00",
            end_at: "2026-10-02T16:00:00+08:00",
            venue_name: "SMU SCIS Building",
            join_link: null,
          },
        },
        201,
      ),
    );

    const confirmation = await registrationApi.register("e1", { dietary: "vegetarian" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/events/e1/registrations");
    expect(JSON.parse(init.body)).toEqual({ answers: { dietary: "vegetarian" } });
    expect((init.headers as Headers).get("X-Attendee-Id")).toBe("attendee-id");
    expect(confirmation).toEqual({
      registrationId: "r1",
      status: "confirmed",
      event: {
        title: "Tech Talk",
        startsAt: "2026-10-02T14:00:00+08:00",
        endsAt: "2026-10-02T16:00:00+08:00",
        venue: "SMU SCIS Building",
        joinUrl: undefined,
      },
    });
  });

  it("joins a waitlist by email with no identity header (D7)", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ registration_id: "r9", status: "waitlisted", position: 4 }, 201));

    await expect(registrationApi.joinWaitlist("e1", "calvin@smu.edu.sg")).resolves.toEqual({
      registrationId: "r9",
      status: "waitlisted",
      position: 4,
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/events/e1/waitlist");
    expect(JSON.parse(init.body)).toEqual({ email: "calvin@smu.edu.sg" });
    expect((init.headers as Headers).get("X-Attendee-Id")).toBeNull();
  });

  it("maps a withdrawal result", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ status: "withdrawn", withdrawn_at: "2026-10-01T02:00:00Z", event_name: "Tech Talk", seats_remaining: 4 }),
    );

    await expect(registrationApi.withdraw("r1")).resolves.toEqual({
      status: "withdrawn",
      withdrawnAt: "2026-10-01T02:00:00Z",
      eventTitle: "Tech Talk",
      seatsRemaining: 4,
    });
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/api/v1/registrations/r1/withdraw");
  });

  it("accepts an offer on its registration", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        registration_id: "r3",
        status: "confirmed",
        event: { name: "Bootcamp", start_at: "x", end_at: "y", venue_name: null, join_link: null },
      }),
    );

    await registrationApi.acceptOffer("r3");
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/api/v1/registrations/r3/accept");
  });

  it("passes API errors through", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ code: "EVENT_FULL", waitlist_available: true }, 409));

    await expect(registrationApi.register("e1", {})).rejects.toMatchObject({
      code: "EVENT_FULL",
      body: { waitlist_available: true },
    });
  });
});
