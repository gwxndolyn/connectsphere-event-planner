import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../../App";
import { type DevRole, setDevRole } from "../../api/client";
import { callsTo, seedBlock, seedBooking, seedRequest, seedVenue, startMockBackend } from "../../test/server";

// US21 (SCRUM-88, PR 2 SCRUM-123): the real App, VenuesPage and VenueCalendar against the fake
// backend, whose calendar route follows the API's rules (backend/tests/venue/test_calendar.py).
// The clock is Wed 14 Oct 2026, noon in Singapore.
startMockBackend();

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-14T04:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

type User = ReturnType<typeof userEvent.setup>;

async function openVenues(role: DevRole) {
  setDevRole(role);
  const user = userEvent.setup();
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Venues" }));
  await screen.findByRole("heading", { name: "Venues" });
  return user;
}

function calendarRegion() {
  return within(screen.getByRole("region", { name: "Availability calendar" }));
}

function lastRange() {
  const call = callsTo("GET", /^\/api\/v1\/venues\/[^/]+\/calendar$/).at(-1)!;
  return { from: call.url.searchParams.get("from"), to: call.url.searchParams.get("to"), user: call.headers.get("X-User-Id") };
}

async function choose(user: User, venue: string) {
  await user.selectOptions(await calendarRegion().findByLabelText("Venue"), venue);
}

describe("venue calendar (US21)", () => {
  it.each(["coordinator", "coordinator_lead", "venue_staff"] as const)(
    "TC-US21-16: is on Venues for the %s role (AC 5, D56)",
    async (role) => {
      seedVenue();
      await openVenues(role);

      expect(await screen.findByRole("heading", { name: "Availability calendar" })).toBeInTheDocument();
    },
  );

  it("TC-US21-16: isn't on Venues for the organiser (AC 5)", async () => {
    seedVenue();
    await openVenues("organiser");

    await screen.findByRole("list", { name: "Venues" });
    expect(screen.queryByRole("heading", { name: "Availability calendar" })).not.toBeInTheDocument();
  });

  it("TC-US21-21: Previous, Today, Next and Week / Month each ask for the right days (AC 1)", async () => {
    const venue = seedVenue();
    // Fri 20 Nov, 10:00–12:00 Singapore.
    seedBooking(seedRequest({ status: "approved", name: "Planning workshop" }), venue);
    const user = await openVenues("venue_staff");

    await choose(user, "SCIS Seminar Room 2-1");
    await calendarRegion().findByText("Nothing booked or blocked at SCIS Seminar Room 2-1 this week.");
    expect(lastRange()).toEqual({ from: "2026-10-12", to: "2026-10-18", user: "venue-staff-id" });

    await user.click(calendarRegion().getByRole("button", { name: "Next" }));
    expect(lastRange()).toMatchObject({ from: "2026-10-19", to: "2026-10-25" });
    await user.click(calendarRegion().getByRole("button", { name: "Previous" }));
    await user.click(calendarRegion().getByRole("button", { name: "Previous" }));
    expect(lastRange()).toMatchObject({ from: "2026-10-05", to: "2026-10-11" });
    await user.click(calendarRegion().getByRole("button", { name: "Today" }));
    expect(lastRange()).toMatchObject({ from: "2026-10-12", to: "2026-10-18" });

    await user.click(calendarRegion().getByRole("button", { name: "Month" }));
    expect(lastRange()).toMatchObject({ from: "2026-09-28", to: "2026-11-01" });
    expect(calendarRegion().getByRole("heading", { name: "October 2026" })).toBeInTheDocument();
    await user.click(calendarRegion().getByRole("button", { name: "Next" }));
    expect(lastRange()).toMatchObject({ from: "2026-10-26", to: "2026-12-06" });

    // The booking is a chip on its own day, by its occupied window (15 min setup and turnaround).
    const friday = within(await calendarRegion().findByRole("group", { name: "Fri, Nov 20" }));
    expect(
      friday.getByRole("button", { name: "Booking (requested): Planning workshop, 10:00 AM – 12:00 PM, occupied 9:45 AM – 12:15 PM" }),
    ).toHaveTextContent("Booking (requested) 9:45 AM – 12:15 PM");

    await user.click(calendarRegion().getByRole("button", { name: "Week" }));
    expect(lastRange()).toMatchObject({ from: "2026-10-26", to: "2026-11-01" });
  });

  it("TC-US21-20: Venue staff see a booking's reference, a coordinator not on another's event (D58)", async () => {
    const venue = seedVenue();
    seedBooking(seedRequest({ status: "approved", name: "Planning workshop" }), venue, {
      starts_at: "2026-10-13T02:00:00Z",
      ends_at: "2026-10-13T04:00:00Z",
    });
    seedBlock(venue, { starts_at: "2026-10-15T05:00:00Z", ends_at: "2026-10-15T07:00:00Z" });

    const user = await openVenues("venue_staff");
    await choose(user, "SCIS Seminar Room 2-1");
    expect(await calendarRegion().findByRole("button", { name: "Unavailable: Aircon repair, 1:00 PM – 3:00 PM" })).toBeInTheDocument();
    await user.click(calendarRegion().getByRole("button", { name: /^Booking \(requested\): Planning workshop/ }));
    expect(screen.getByRole("dialog")).toHaveTextContent("VB-2026-000001");
  });

  it("TC-US21-20: a coordinator sees another coordinator's booking without its reference (D58)", async () => {
    const venue = seedVenue();
    seedBooking(seedRequest({ status: "approved", name: "Planning workshop" }), venue, {
      starts_at: "2026-10-13T02:00:00Z",
      ends_at: "2026-10-13T04:00:00Z",
    });

    const user = await openVenues("coordinator");
    await choose(user, "SCIS Seminar Room 2-1");
    await user.click(await calendarRegion().findByRole("button", { name: /^Booking \(requested\): Planning workshop/ }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Planning workshop");
    expect(dialog).not.toHaveTextContent("VB-");
    expect(lastRange().user).toBe("coordinator-id");
  });
});
