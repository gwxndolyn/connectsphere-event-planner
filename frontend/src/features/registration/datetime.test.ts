import { describe, expect, it } from "vitest";
import {
  formatEventDate,
  formatEventTime,
  formatEventTimeRange,
  formatInstantDateTime,
  formatInstantTime,
  toTimed,
} from "./datetime";

// 06:00 UTC is 14:00 in Singapore; the formatters must show Singapore time whatever the test
// machine's zone (TC-X-01).
const EVENT = { startsAt: "2026-10-02T06:00:00Z", endsAt: "2026-10-02T08:00:00Z" };

describe("event date and time formatting", () => {
  it("shows the date in Asia/Singapore", () => {
    expect(formatEventDate(EVENT)).toBe("Fri, Oct 2");
  });

  it("shows the start time in Asia/Singapore", () => {
    expect(formatEventTime(EVENT)).toBe("2:00 PM");
  });

  it("shows the start and end as a range", () => {
    expect(formatEventTimeRange(EVENT)).toBe("2:00 PM – 4:00 PM");
  });

  it("rolls the date over at Singapore midnight, not UTC midnight", () => {
    // 17:30 UTC on 1 Oct is 01:30 on 2 Oct in Singapore.
    expect(formatEventDate({ startsAt: "2026-10-01T17:30:00Z", endsAt: "2026-10-01T18:30:00Z" })).toBe("Fri, Oct 2");
  });
});

describe("instants", () => {
  it("formats an offer deadline with its day", () => {
    expect(formatInstantDateTime("2026-10-03T01:00:00Z")).toBe("Sat, Oct 3, 9:00 AM");
  });

  it("formats a withdrawal time", () => {
    expect(formatInstantTime("2026-10-03T01:05:00Z")).toBe("9:05 AM");
  });
});

describe("toTimed", () => {
  it("turns My events' Singapore wall-clock strings into offset timestamps", () => {
    expect(toTimed("2026-10-02", "14:00", "16:00")).toEqual({
      startsAt: "2026-10-02T14:00:00+08:00",
      endsAt: "2026-10-02T16:00:00+08:00",
    });
  });

  it("round-trips through the formatters unchanged", () => {
    const timed = toTimed("2026-10-02", "14:00", "16:00");
    expect(formatEventDate(timed)).toBe("Fri, Oct 2");
    expect(formatEventTimeRange(timed)).toBe("2:00 PM – 4:00 PM");
  });
});
