import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import {
  bookingApi,
  bookingErrorMessage,
  bookingFieldErrors,
  bookingStatusLabel,
  formatBookingWindow,
  missingForVenue,
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
