import { describe, expect, it } from "vitest";
import {
  addDays,
  closedBands,
  daySegments,
  hourSpan,
  monthDays,
  place,
  rangeFor,
  rangeTitle,
  singaporeToday,
  step,
  weekDays,
} from "./calendarGrid";
import type { CalendarItem, CalendarVenue } from "./types";

// US21 (SCRUM-88, PR 2 SCRUM-123): the calendar's date maths, all in Singapore days (D9, D61).

const VENUE: CalendarVenue = {
  id: "venue-1",
  name: "Hall A",
  is_active: true,
  opens_at: "08:00:00",
  closes_at: "20:00:00",
  setup_minutes: 30,
  turnaround_minutes: 15,
};

function booking(startsAt: string, endsAt: string, occupiedStartsAt: string, occupiedEndsAt: string): CalendarItem {
  return {
    kind: "booking",
    label: "Booking",
    starts_at: startsAt,
    ends_at: endsAt,
    occupied: { starts_at: occupiedStartsAt, ends_at: occupiedEndsAt },
    booking: {
      id: "booking-1",
      reference: null,
      status: "approved",
      event: { name: "Design Review", request_reference: null, status: "approved" },
    },
    note: null,
  };
}

function block(startsAt: string, endsAt: string): CalendarItem {
  return {
    kind: "block",
    label: "Unavailable",
    starts_at: startsAt,
    ends_at: endsAt,
    occupied: { starts_at: startsAt, ends_at: endsAt },
    booking: null,
    note: "Aircon repair",
  };
}

describe("TC-US21-15: weeks, months and the range asked for (AC 1)", () => {
  it("takes today's Singapore day, which starts at 16:00 UTC", () => {
    expect(singaporeToday(Date.parse("2026-10-13T15:59:00Z"))).toBe("2026-10-13");
    expect(singaporeToday(Date.parse("2026-10-13T16:00:00Z"))).toBe("2026-10-14");
  });

  it("adds days across a month and a year", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2027-01-01", -1)).toBe("2026-12-31");
  });

  it("makes a week Monday to Sunday, from any day in it", () => {
    const week = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18"];
    expect(weekDays("2026-10-14")).toEqual(week);
    expect(weekDays("2026-10-12")).toEqual(week);
    expect(weekDays("2026-10-18")).toEqual(week);
    expect(weekDays("2027-01-01")[0]).toBe("2026-12-28");
    expect(weekDays("2027-01-01")[6]).toBe("2027-01-03");
  });

  it("makes a month the full weeks covering it: four, five or six", () => {
    const october = monthDays("2026-10-14");
    expect([october[0], october.at(-1), october.length]).toEqual(["2026-09-28", "2026-11-01", 35]);
    // 1 Nov 2026 is a Sunday: six weeks, the API's 42-day limit (D61).
    const november = monthDays("2026-11-20");
    expect([november[0], november.at(-1), november.length]).toEqual(["2026-10-26", "2026-12-06", 42]);
    const february = monthDays("2027-02-10");
    expect([february[0], february.at(-1), february.length]).toEqual(["2027-02-01", "2027-02-28", 28]);
  });

  it("asks the API for exactly the days drawn", () => {
    expect(rangeFor("week", "2026-10-14")).toEqual({ from: "2026-10-12", to: "2026-10-18" });
    expect(rangeFor("month", "2026-11-20")).toEqual({ from: "2026-10-26", to: "2026-12-06" });
  });

  it("steps a week by seven days and a month to the first of the next or last", () => {
    expect(step("week", "2026-10-14", 1)).toBe("2026-10-21");
    expect(step("week", "2026-10-14", -1)).toBe("2026-10-07");
    expect(step("month", "2026-10-14", 1)).toBe("2026-11-01");
    expect(step("month", "2026-01-31", -1)).toBe("2025-12-01");
  });

  it("titles a week by its days and a month by its name", () => {
    expect(rangeTitle("week", "2026-10-14")).toBe("Mon, Oct 12 – Sun, Oct 18");
    expect(rangeTitle("month", "2026-10-14")).toBe("October 2026");
  });
});

describe("daySegments: each item's occupied window, day by day (TC-US21-17, AC 2)", () => {
  it("places a booking by its occupied window, with its setup and turnaround", () => {
    // 10:00–12:00 Singapore, occupied 09:30–12:15.
    const item = booking("2026-10-12T02:00:00Z", "2026-10-12T04:00:00Z", "2026-10-12T01:30:00Z", "2026-10-12T04:15:00Z");

    expect(daySegments([item], "2026-10-12")).toEqual([
      { item, startMinute: 570, endMinute: 735, setupMinutes: 30, turnaroundMinutes: 15, lane: 0, lanes: 1 },
    ]);
    expect(daySegments([item], "2026-10-13")).toEqual([]);
  });

  it("splits an item that runs past midnight, setup on the first day and turnaround on the next", () => {
    // 21:30–00:45 Singapore, occupied 21:00–01:00.
    const item = booking("2026-10-12T13:30:00Z", "2026-10-12T16:45:00Z", "2026-10-12T13:00:00Z", "2026-10-12T17:00:00Z");

    expect(daySegments([item], "2026-10-12")).toMatchObject([
      { startMinute: 1260, endMinute: 1440, setupMinutes: 30, turnaroundMinutes: 0 },
    ]);
    expect(daySegments([item], "2026-10-13")).toMatchObject([
      { startMinute: 0, endMinute: 60, setupMinutes: 0, turnaroundMinutes: 15 },
    ]);
  });

  it("puts overlapping items side by side, and a block has no buffers", () => {
    const closure = block("2026-10-12T00:00:00Z", "2026-10-12T10:00:00Z");
    const item = booking("2026-10-12T02:00:00Z", "2026-10-12T04:00:00Z", "2026-10-12T01:30:00Z", "2026-10-12T04:15:00Z");

    expect(daySegments([item, closure], "2026-10-12")).toMatchObject([
      { item: closure, startMinute: 480, endMinute: 1080, setupMinutes: 0, turnaroundMinutes: 0, lane: 0, lanes: 2 },
      { item, lane: 1, lanes: 2 },
    ]);
  });
});

describe("hours drawn and shaded (TC-US21-19, D61)", () => {
  it("draws an hour either side of the opening hours, widened to fit any item", () => {
    expect(hourSpan(VENUE, [])).toEqual({ start: 7, end: 21 });
    const early = booking("2026-10-12T22:00:00Z", "2026-10-12T22:30:00Z", "2026-10-12T21:30:00Z", "2026-10-12T22:45:00Z");
    // 05:30–06:45 the next day: from 05:00.
    expect(hourSpan(VENUE, daySegments([early], "2026-10-13"))).toEqual({ start: 5, end: 21 });
    expect(hourSpan({ ...VENUE, opens_at: "00:00:00", closes_at: "23:30:00" }, [])).toEqual({ start: 0, end: 24 });
  });

  it("shades the hours before opening and after closing", () => {
    expect(closedBands(VENUE, { start: 7, end: 21 })).toEqual([
      { startMinute: 420, endMinute: 480 },
      { startMinute: 1200, endMinute: 1260 },
    ]);
    expect(closedBands({ ...VENUE, opens_at: "00:00:00", closes_at: "24:00:00" }, { start: 0, end: 24 })).toEqual([]);
  });

  it("places a window as a share of the hours drawn", () => {
    const { top, height } = place(570, 735, { start: 7, end: 21 });
    expect(top).toBeCloseTo((150 / 840) * 100);
    expect(height).toBeCloseTo((165 / 840) * 100);
  });
});
