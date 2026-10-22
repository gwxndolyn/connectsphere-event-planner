import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { describeCriteria, hhmm, venueApi, venueErrorMessage, venueFieldErrors } from "./api";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ venues: [], criteria: {} }), { headers: { "Content-Type": "application/json" } }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

const FORM = {
  date: "2026-10-10",
  startTime: "10:00",
  endTime: "12:00",
  attendees: "30",
  location: "",
  facilities: [],
  accessibility: [],
};

function sentUrl(): URL {
  return new URL(fetchMock.mock.calls[0][0]);
}

describe("venueApi.search (US2)", () => {
  it("sends the core criteria to /venues/available with X-User-Id", async () => {
    await venueApi.search(FORM);

    const url = sentUrl();
    expect(url.pathname).toBe("/api/v1/venues/available");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      date: "2026-10-10",
      start_time: "10:00",
      end_time: "12:00",
      attendees: "30",
    });
    expect((fetchMock.mock.calls[0][1].headers as Headers).get("X-User-Id")).toBe("organiser-id");
  });

  it("repeats each facility and accessibility tag and trims the location", async () => {
    await venueApi.search({ ...FORM, location: "  Library ", facilities: ["projector", "stage"], accessibility: ["lift"] });

    const url = sentUrl();
    expect(url.searchParams.get("location")).toBe("Library");
    expect(url.searchParams.getAll("facilities")).toEqual(["projector", "stage"]);
    expect(url.searchParams.getAll("accessibility")).toEqual(["lift"]);
  });

  it("leaves blank fields out so the API names them as missing", async () => {
    await venueApi.search({ ...FORM, date: "", attendees: "  " });

    const url = sentUrl();
    expect(url.searchParams.has("date")).toBe(false);
    expect(url.searchParams.has("attendees")).toBe(false);
    expect(url.searchParams.has("location")).toBe(false);
  });
});

describe("describeCriteria (US2 AC 7)", () => {
  it("lists the core criteria with HH:MM times", () => {
    expect(
      describeCriteria({
        date: "2026-10-10",
        start_time: "10:00:00",
        end_time: "12:00:00",
        attendees: 30,
        location: null,
        facilities: [],
        accessibility: [],
      }),
    ).toEqual(["Date: 2026-10-10", "Time: 10:00–12:00", "Expected attendance: 30"]);
  });

  it("adds the optional filters, with readable tag labels", () => {
    expect(
      describeCriteria({
        date: "2026-10-10",
        start_time: "10:00:00",
        end_time: "12:00:00",
        attendees: 500,
        location: "Library",
        facilities: ["wifi", "sound_system"],
        accessibility: ["step_free_entrance"],
      }).slice(3),
    ).toEqual(["Location: Library", "Facilities: Wi-Fi, Sound system", "Accessibility: Step-free entrance"]);
  });
});

describe("errors", () => {
  it("maps INVALID_VENUE_SEARCH to a message and per-field errors", () => {
    const error = new ApiError(422, "INVALID_VENUE_SEARCH", ["end_time"], {
      errors: { end_time: "The end time must be after the start time (events can't cross midnight)." },
    });

    expect(venueErrorMessage(error)).toBe("Review the fields marked below and try again.");
    expect(venueFieldErrors(error)).toEqual({
      end_time: "The end time must be after the start time (events can't cross midnight).",
    });
  });

  it("marks each missing criterion as required", () => {
    expect(venueFieldErrors(new ApiError(422, "MISSING_REQUIRED_FIELD", ["date", "attendees"]))).toEqual({
      date: "Required.",
      attendees: "Required.",
    });
  });
});

it("hhmm trims seconds", () => {
  expect(hhmm("08:00:00")).toBe("08:00");
});
