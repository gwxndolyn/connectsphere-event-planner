import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import {
  bookingApi,
  bookingErrorMessage,
  bookingFieldErrors,
  bookingStatusLabel,
  decisionErrorMessage,
  formatBookingWindow,
  formatOccupied,
  formatVenueTime,
  missingForVenue,
  occupiedPreview,
  toBookingBody,
} from "./bookingApi";
import type { BookingFormValues } from "./bookingTypes";
import type { Venue } from "./types";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  // A fresh Response per call: a body can only be read once.
  fetchMock = vi.fn().mockImplementation(
    async () => new Response(JSON.stringify({ bookings: [] }), { headers: { "Content-Type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

const FORM: BookingFormValues = {
  venueId: "venue-1",
  date: "2026-11-20",
  startTime: "10:00",
  endTime: "12:00",
  attendees: "30",
  roomLayout: "classroom",
  facilities: ["projector"],
  accessibility: ["wheelchair"],
  specialRequirements: "  Lectern at the front  ",
};

const VENUE: Venue = {
  id: "venue-1",
  name: "Hall A",
  location: "Building 1",
  capacity: 40,
  facilities: ["projector", "wifi"],
  accessibility_features: [],
  room_layouts: ["theatre"],
  opens_at: "08:00:00",
  closes_at: "22:00:00",
  setup_minutes: 0,
  turnaround_minutes: 0,
  is_active: true,
};

function sent(): { url: URL; init: RequestInit } {
  return { url: new URL(fetchMock.mock.calls[0][0]), init: fetchMock.mock.calls[0][1] };
}

describe("toBookingBody (US22 AC 2)", () => {
  it("sends the window as Singapore times with an offset, and every field the API takes", () => {
    expect(toBookingBody("event-1", FORM)).toEqual({
      event_id: "event-1",
      venue_id: "venue-1",
      starts_at: "2026-11-20T10:00:00+08:00",
      ends_at: "2026-11-20T12:00:00+08:00",
      expected_attendees: 30,
      room_layout: "classroom",
      required_facilities: ["projector"],
      required_accessibility_features: ["wheelchair"],
      special_requirements: "Lectern at the front",
    });
  });

  it("leaves blank fields out, so the API's MISSING_REQUIRED_FIELD names each one", () => {
    const body = toBookingBody("event-1", {
      ...FORM,
      venueId: "",
      date: "",
      attendees: " ",
      roomLayout: "",
      specialRequirements: "   ",
    });

    expect(body).toEqual({
      event_id: "event-1",
      required_facilities: ["projector"],
      required_accessibility_features: ["wheelchair"],
    });
  });
});

describe("bookingApi", () => {
  it("posts a request with the coordinator's X-User-Id", async () => {
    await bookingApi.create(toBookingBody("event-1", FORM));

    const { url, init } = sent();
    expect(url.pathname).toBe("/api/v1/venue-bookings");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body)).starts_at).toBe("2026-11-20T10:00:00+08:00");
    expect((init.headers as Headers).get("X-User-Id")).toBe("organiser-id");
  });

  it("withdraws, and reads an event's bookings and the pending list", async () => {
    await bookingApi.withdraw("booking-1");
    expect(sent().url.pathname).toBe("/api/v1/venue-bookings/booking-1/withdraw");

    fetchMock.mockClear();
    await bookingApi.forEvent("event-1");
    expect(sent().url.pathname).toBe("/api/v1/events/event-1/venue-bookings");

    fetchMock.mockClear();
    await bookingApi.pending();
    expect(sent().url.pathname).toBe("/api/v1/venue-bookings/pending");
  });

  it("reads a booking's evaluation (US13 AC 4, D36)", async () => {
    await bookingApi.evaluation("booking-1");
    expect(sent().url.pathname).toBe("/api/v1/venue-bookings/booking-1/evaluation");
    expect(sent().init.method ?? "GET").toBe("GET");
  });
});

describe("missingForVenue (AC 3: warned, but can still submit)", () => {
  it("names each required facility, feature and the layout the venue lacks", () => {
    expect(
      missingForVenue({ ...FORM, facilities: ["projector", "stage", "wifi"], accessibility: ["wheelchair"] }, VENUE),
    ).toEqual(["Stage", "Wheelchair", "Classroom layout"]);
  });

  it("is empty when the venue has everything asked for", () => {
    expect(missingForVenue({ ...FORM, roomLayout: "theatre", accessibility: [] }, VENUE)).toEqual([]);
  });
});

describe("booking errors", () => {
  it("puts VENUE_CAPACITY_EXCEEDED's message on attendance", () => {
    const error = new ApiError(422, "VENUE_CAPACITY_EXCEEDED", ["expected_attendees"], {
      capacity: 40,
      message: "Expected attendance is more than this venue's capacity of 40.",
    });

    expect(bookingFieldErrors(error)).toEqual({
      expected_attendees: "Expected attendance is more than this venue's capacity of 40.",
    });
    expect(bookingErrorMessage(error)).toBe("Expected attendance is more than this venue's capacity of 40.");
  });

  it("names VENUE_UNAVAILABLE's clashing window in Singapore time, on the start time", () => {
    const error = new ApiError(409, "VENUE_UNAVAILABLE", [], {
      conflict: { starts_at: "2026-11-20T01:00:00+00:00", ends_at: "2026-11-20T05:00:00+00:00" },
    });

    expect(bookingErrorMessage(error)).toBe(
      "This venue is already booked or unavailable on Fri, Nov 20, 9:00 AM – 1:00 PM. Choose another time or venue.",
    );
    expect(bookingFieldErrors(error)).toEqual({ starts_at: "Clashes with Fri, Nov 20, 9:00 AM – 1:00 PM." });
  });

  it("maps INVALID_BOOKING's errors and MISSING_REQUIRED_FIELD's fields", () => {
    expect(
      bookingFieldErrors(
        new ApiError(422, "INVALID_BOOKING", ["starts_at", "room_layout"], {
          errors: { starts_at: "Start time can't be in the past.", room_layout: "Unknown room layout." },
        }),
      ),
    ).toEqual({ starts_at: "Start time can't be in the past.", room_layout: "Unknown room layout." });
    expect(bookingFieldErrors(new ApiError(422, "MISSING_REQUIRED_FIELD", ["venue_id", "ends_at"]))).toEqual({
      venue_id: "Required.",
      ends_at: "Required.",
    });
  });

  it("explains the codes that aren't about one field", () => {
    expect(bookingErrorMessage(new ApiError(409, "BOOKING_NOT_PENDING", [], { status: "approved" }))).toBe(
      "This booking is no longer pending (it's approved now), so it can't be withdrawn.",
    );
    expect(bookingErrorMessage(new ApiError(409, "EVENT_NOT_BOOKABLE", [], { status: "cancelled" }))).toMatch(
      /approved events or events in planning/,
    );
    expect(bookingErrorMessage(new ApiError(404, "NOT_FOUND"))).toMatch(/no longer available/);
    expect(bookingErrorMessage(new Error("offline"))).toMatch(/Check the backend connection/);
  });
});

describe("formatting", () => {
  it("shows a booking's window and status in Singapore terms", () => {
    expect(formatBookingWindow({ starts_at: "2026-11-20T02:00:00Z", ends_at: "2026-11-20T04:00:00Z" })).toBe(
      "Fri, Nov 20, 10:00 AM – 12:00 PM",
    );
    expect(bookingStatusLabel("requested")).toBe("Requested");
    expect(bookingStatusLabel("withdrawn")).toBe("Withdrawn");
  });
});

describe("occupied window (US13, SCRUM-116)", () => {
  it("adds the venue's setup before and turnaround after: 10:00–12:00 with 30/45 is 09:30–12:45 (TC-US13-16, AC 2)", () => {
    const occupied = occupiedPreview(FORM, { ...VENUE, setup_minutes: 30, turnaround_minutes: 45 });

    expect(occupied).toEqual({ starts_at: "2026-11-20T01:30:00.000Z", ends_at: "2026-11-20T04:45:00.000Z" });
    expect(formatOccupied({ occupied_starts_at: occupied!.starts_at, occupied_ends_at: occupied!.ends_at })).toBe(
      "9:30 AM – 12:45 PM",
    );
  });

  it("is the plain window with no buffers, and nothing until the times make a window", () => {
    expect(occupiedPreview(FORM, VENUE)).toEqual({ starts_at: "2026-11-20T02:00:00.000Z", ends_at: "2026-11-20T04:00:00.000Z" });
    expect(occupiedPreview({ ...FORM, endTime: "" }, VENUE)).toBeNull();
    expect(occupiedPreview({ ...FORM, date: "" }, VENUE)).toBeNull();
    expect(occupiedPreview({ ...FORM, endTime: "10:00" }, VENUE)).toBeNull();
  });

  it("shows a venue's hours as the screens show times", () => {
    expect(formatVenueTime("08:00:00")).toBe("8:00 AM");
    expect(formatVenueTime("18:30:00")).toBe("6:30 PM");
  });
});

describe("US13 booking errors (SCRUM-116)", () => {
  const unavailable = (kind: "booking" | "block") =>
    new ApiError(409, "VENUE_UNAVAILABLE", [], {
      conflict: {
        kind,
        starts_at: "2026-11-20T02:00:00+00:00",
        ends_at: "2026-11-20T04:00:00+00:00",
        occupied: { starts_at: "2026-11-20T01:45:00+00:00", ends_at: "2026-11-20T04:15:00+00:00" },
        overlap: { starts_at: "2026-11-20T04:00:00+00:00", ends_at: "2026-11-20T04:15:00+00:00" },
      },
      occupied: { starts_at: "2026-11-20T04:00:00+00:00", ends_at: "2026-11-20T05:15:00+00:00" },
    });

  it("names VENUE_UNAVAILABLE's overlap period, but no other booking's reference (TC-US13-17, AC 4, D35)", () => {
    expect(bookingErrorMessage(unavailable("booking"))).toBe(
      "This venue is already booked on Fri, Nov 20, 10:00 AM – 12:00 PM. With setup and turnaround, that overlaps your request 12:00 PM – 12:15 PM. Choose another time or venue.",
    );
    expect(bookingFieldErrors(unavailable("booking"))).toEqual({
      starts_at: "With setup and turnaround, overlaps another booking 12:00 PM – 12:15 PM.",
    });
    expect(bookingErrorMessage(unavailable("block"))).toMatch(/^This venue is closed on Fri, Nov 20, 10:00 AM – 12:00 PM\./);
    expect(bookingFieldErrors(unavailable("block")).starts_at).toBe(
      "With setup and turnaround, overlaps a venue closure 12:00 PM – 12:15 PM.",
    );
  });

  it("puts VENUE_OUTSIDE_HOURS on the time field that breaches, with the hours (TC-US13-17, AC 5)", () => {
    const error = (fields: string[]) =>
      new ApiError(422, "VENUE_OUTSIDE_HOURS", fields, {
        opens_at: "09:00:00",
        closes_at: "18:00:00",
        occupied: { starts_at: "2026-11-20T07:40:00+00:00", ends_at: "2026-11-20T10:10:00+00:00" },
      });

    expect(bookingFieldErrors(error(["ends_at"]))).toEqual({ ends_at: "With turnaround, ends after the venue closes at 6:00 PM." });
    expect(bookingFieldErrors(error(["starts_at", "ends_at"]))).toEqual({
      starts_at: "With setup, starts before the venue opens at 9:00 AM.",
      ends_at: "With turnaround, ends after the venue closes at 6:00 PM.",
    });
    expect(bookingErrorMessage(error(["ends_at"]))).toBe(
      "With setup and turnaround the venue would be occupied 3:40 PM – 6:10 PM, outside its opening hours of 9:00 AM – 6:00 PM. Choose times that fit.",
    );
  });

  it("explains an approval refused for opening hours (TC-US4-03, D32)", () => {
    const error = new ApiError(409, "VENUE_OUTSIDE_HOURS", ["ends_at"], {
      opens_at: "09:00:00",
      closes_at: "11:00:00",
      occupied: { starts_at: "2026-11-20T00:30:00+00:00", ends_at: "2026-11-20T03:15:00+00:00" },
    });

    expect(decisionErrorMessage(error)).toBe(
      "Can't approve: with setup and turnaround the venue would be occupied 8:30 AM – 11:15 AM, outside its opening hours of 9:00 AM – 11:00 AM now. Reject the request instead.",
    );
  });
});
