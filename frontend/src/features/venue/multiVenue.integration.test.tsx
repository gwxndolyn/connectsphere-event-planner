import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { callsTo, COORDINATOR_PERSON, db, seedBooking, seedRequest, seedVenue, startMockBackend } from "../../test/server";

// US24 (SCRUM-92, PR 3 SCRUM-129), TC-US24-25: the real App and screens against the fake backend,
// whose rules follow PR 2's API (backend/tests/venue/test_multi_venue_api.py): the primary venue
// (D68), withdrawing an approved venue (D69), the Organiser's read (D71) and Venue staff's
// preparation status (D73, D78).
startMockBackend();

afterEach(() => {
  vi.useRealTimers();
});

type User = ReturnType<typeof userEvent.setup>;

const MINE = { coordinator: { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name } };

/** Approved, assigned to the coordinator, created by the organiser: a main hall (approved, primary) and a breakout. */
function seedConference() {
  const request = seedRequest({ status: "approved", name: "Data Conference", expected_attendees: 60, ...MINE });
  const hall = seedVenue({ name: "Main Hall", capacity: 200 });
  const room = seedVenue({ name: "Breakout Room", capacity: 40 });
  const main = seedBooking(request, hall, {
    status: "approved",
    purpose: "Main hall",
    is_primary: true,
    expected_attendees: 60,
    decided_at: "2026-10-02T02:00:00Z",
    decided_by_user_id: "venue-staff-id",
    preparation_status: "in_progress",
  });
  const breakout = seedBooking(request, room, {
    starts_at: "2026-11-20T05:00:00Z",
    ends_at: "2026-11-20T07:00:00Z",
    purpose: "Breakout A",
    is_primary: false,
    expected_attendees: 30,
  });
  return { request, main, breakout };
}

async function open(user: User, role: "coordinator" | "organiser", name: string) {
  setDevRole(role);
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
}

function venueRow(list: string, name: RegExp) {
  return within(screen.getByRole("list", { name: list })).getByRole("listitem", { name });
}

describe("several venues for one event (US24, TC-US24-25)", () => {
  it("the coordinator moves the primary venue and withdraws an approved one", async () => {
    const { main, breakout } = seedConference();
    const user = userEvent.setup();
    await open(user, "coordinator", "Data Conference");

    const list = "This event's venue bookings";
    await screen.findByRole("list", { name: list });
    expect(within(venueRow(list, /^Main Hall/)).getByText("Primary")).toBeInTheDocument();

    await user.click(within(venueRow(list, /^Breakout Room/)).getByRole("button", { name: "Make primary" }));
    expect(await within(venueRow(list, /^Breakout Room/)).findByText("Primary")).toBeInTheDocument();
    expect(within(venueRow(list, /^Main Hall/)).queryByText("Primary")).not.toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/venue-bookings/${breakout.id}/make-primary`)).toHaveLength(1);

    await user.click(within(venueRow(list, /^Main Hall/)).getByRole("button", { name: "Withdraw" }));
    await user.click(within(screen.getByRole("dialog", { name: "Withdraw this approved venue?" })).getByRole("button", { name: "Withdraw venue" }));
    expect(await within(venueRow(list, /^Main Hall/)).findByText("Withdrawn")).toBeInTheDocument();
    expect(db.bookings.find((b) => b.id === main.id)?.status).toBe("withdrawn");
    expect(within(venueRow(list, /^Breakout Room/)).getByText("Requested")).toBeInTheDocument();
  });

  it("the Organiser reads the venues of their approved event, with no actions", async () => {
    seedConference();
    const user = userEvent.setup();
    await open(user, "organiser", "Data Conference");

    const list = "This event's venues";
    expect(await screen.findByRole("list", { name: list })).toBeInTheDocument();
    expect(venueRow(list, /^Main hall/)).toHaveTextContent("Preparation: In progress");
    expect(venueRow(list, /^Breakout A/)).toHaveTextContent("Next: Waiting for Venue staff");
    expect(screen.getByRole("region", { name: "Venue arrangements" })).toHaveTextContent("Venues not arranged");
    expect(within(screen.getByRole("region", { name: "Venues" })).queryByRole("button")).not.toBeInTheDocument();
    const [read] = callsTo("GET", /\/api\/v1\/events\/[^/]+\/venue-bookings$/);
    expect(read.headers.get("X-User-Id")).toBe("organiser-id");
  });

  it("Venue staff set an approved venue's preparation status from the calendar", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-18T04:00:00Z"));
    const { main } = seedConference();
    setDevRole("venue_staff");
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Venues" }));

    const calendar = within(await screen.findByRole("region", { name: "Availability calendar" }));
    await user.selectOptions(await calendar.findByRole("combobox", { name: /^Venue/ }), "Main Hall");
    await user.click(await calendar.findByRole("button", { name: /^Booking: Data Conference/ }));
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByRole("combobox", { name: "Preparation" })).toHaveValue("in_progress");
    await user.selectOptions(dialog.getByRole("combobox", { name: "Preparation" }), "ready");
    await user.click(dialog.getByRole("button", { name: "Save preparation" }));

    expect(await dialog.findByRole("status")).toHaveTextContent("Preparation saved: Ready.");
    expect(db.bookings.find((b) => b.id === main.id)?.preparation_status).toBe("ready");
  });
});
