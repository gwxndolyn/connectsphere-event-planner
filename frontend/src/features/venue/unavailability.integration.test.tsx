import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, onTestFinished, vi } from "vitest";
import App from "../../App";
import { setDevRole, type DevRole } from "../../api/client";
import { callsTo, COORDINATOR_PERSON, seedBlock, seedBooking, seedRequest, seedVenue, startMockBackend } from "../../test/server";
import { endBeforeStart, toBlockBody } from "./blockApi";

// US23a (SCRUM-90): the real App, Venue staff's Venues screen and the coordinator's review screen against the fake
// backend. Which bookings a period overlaps, the reasons, and the refusals are the API's
// (backend/tests/venue/test_unavailability.py); these check what the screens send and show.
startMockBackend();

const MINE = { coordinator: { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name } };

async function signIn(role: DevRole, screenName: string) {
  setDevRole(role);
  const user = userEvent.setup();
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: screenName }));
  return user;
}

function panel() {
  return within(screen.getByRole("region", { name: "Mark a venue unavailable" }));
}

function bookings() {
  return within(screen.getByRole("region", { name: "Venue bookings" }));
}

describe("venue unavailability (US23a)", () => {
  it("TC-US23A-13: Venue staff mark a venue unavailable and see the bookings that need rearranging (AC 1, 3, 4)", async () => {
    const event = seedRequest({ status: "planning", name: "Alumni Night", ...MINE });
    const venue = seedVenue({ name: "Hall A" });
    // 20 Nov, 10:00–12:00 Singapore.
    const affected = seedBooking(event, venue, { status: "approved" });
    const user = await signIn("venue_staff", "Venues");

    await user.click(await panel().findByRole("button", { name: "Mark unavailable" }));
    await user.selectOptions(await panel().findByLabelText("Venue"), await panel().findByRole("option", { name: "Hall A" }));
    await user.type(panel().getByLabelText("Start date"), "2026-11-20");
    await user.clear(panel().getByLabelText("Start time"));
    await user.type(panel().getByLabelText("Start time"), "08:00");
    // The end date follows the start date the first time.
    expect(panel().getByLabelText("End date")).toHaveValue("2026-11-20");
    await user.selectOptions(panel().getByLabelText("Reason"), "equipment_failure");
    await user.type(panel().getByLabelText("Note (optional)"), "Projector failed");
    await user.click(panel().getByRole("button", { name: "Mark unavailable" }));

    const status = await panel().findByRole("status");
    expect(status).toHaveTextContent(/Hall A is unavailable from .* to .* \(Equipment failure\)\./);
    expect(status).toHaveTextContent("1 booking needs rearrangement. Each event's coordinator and organiser have been told.");
    expect(within(status).getByRole("list", { name: "Bookings needing rearrangement" })).toHaveTextContent(
      `${affected.reference}: Alumni Night`,
    );
    const [sent] = callsTo("POST", `/api/v1/venues/${venue.id}/blocks`);
    expect(sent.body).toEqual({
      starts_at: "2026-11-20T08:00:00+08:00",
      ends_at: "2026-11-20T18:00:00+08:00",
      reason: "equipment_failure",
      note: "Projector failed",
    });
  });

  it("TC-US23A-13: a booking an earlier period already marked is listed apart, as nobody is told again (D115)", async () => {
    const event = seedRequest({ status: "planning", name: "Alumni Night", ...MINE });
    const venue = seedVenue({ name: "Hall A" });
    // 20 Nov, 10:00–12:00 Singapore.
    const marked = seedBooking(event, venue, { status: "approved" });
    seedBlock(venue, { affects: [marked.id] });
    const user = await signIn("venue_staff", "Venues");

    await user.click(await panel().findByRole("button", { name: "Mark unavailable" }));
    await user.selectOptions(await panel().findByLabelText("Venue"), await panel().findByRole("option", { name: "Hall A" }));
    await user.type(panel().getByLabelText("Start date"), "2026-11-20");
    await user.selectOptions(panel().getByLabelText("Reason"), "renovation");
    await user.click(panel().getByRole("button", { name: "Mark unavailable" }));

    const status = await panel().findByRole("status");
    expect(status).toHaveTextContent("No other bookings or holds were affected.");
    expect(within(status).getByRole("list", { name: "Bookings already needing rearrangement" })).toHaveTextContent(
      `${marked.reference}: Alumni Night`,
    );
    expect(callsTo("POST", `/api/v1/venues/${venue.id}/blocks`)).toHaveLength(1);
  });

  it("TC-US23A-14: an end before the start is refused on the end date, and nothing is sent (AC 2)", async () => {
    const venue = seedVenue({ name: "Hall A" });
    const user = await signIn("venue_staff", "Venues");

    await user.click(await panel().findByRole("button", { name: "Mark unavailable" }));
    await user.selectOptions(await panel().findByLabelText("Venue"), await panel().findByRole("option", { name: "Hall A" }));
    await user.type(panel().getByLabelText("Start date"), "2026-11-20");
    await user.clear(panel().getByLabelText("End time"));
    await user.type(panel().getByLabelText("End time"), "08:00");
    await user.selectOptions(panel().getByLabelText("Reason"), "maintenance");
    await user.click(panel().getByRole("button", { name: "Mark unavailable" }));

    expect(await panel().findByRole("alert")).toHaveTextContent("Review the fields marked below and try again.");
    expect(panel().getByLabelText("End date")).toHaveAttribute("aria-invalid", "true");
    expect(panel().getByText("The end must be after the start.")).toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/venues/${venue.id}/blocks`)).toHaveLength(0);
  });

  it("TC-US23A-15: a missing reason is marked on its field (AC 1)", async () => {
    seedVenue({ name: "Hall A" });
    const user = await signIn("venue_staff", "Venues");

    await user.click(await panel().findByRole("button", { name: "Mark unavailable" }));
    await user.selectOptions(await panel().findByLabelText("Venue"), await panel().findByRole("option", { name: "Hall A" }));
    await user.type(panel().getByLabelText("Start date"), "2026-11-20");
    await user.click(panel().getByRole("button", { name: "Mark unavailable" }));

    expect(await panel().findByRole("alert")).toHaveTextContent("Complete the fields marked below.");
    expect(panel().getByLabelText("Reason")).toHaveAttribute("aria-invalid", "true");
  });

  it("TC-US23A-16: the coordinator sees Needs rearrangement with the period and reason, and can't confirm a marked hold (AC 3, 4)", async () => {
    const event = seedRequest({ status: "planning", name: "Alumni Night", ...MINE });
    const venue = seedVenue({ name: "Hall A" });
    const approved = seedBooking(event, venue, { status: "approved", is_primary: true });
    const held = seedBooking(event, seedVenue({ name: "Hall B" }), {
      status: "held",
      is_primary: false,
      requested_by_user_id: "venue-staff-id",
      held_by_user_id: "venue-staff-id",
      hold_expires_at: "2026-11-10T09:00:00Z",
    });
    seedBlock(venue, { reason: "safety", note: "Ceiling inspection", affects: [approved.id] });
    seedBlock(seedVenue({ name: "Hall B closed" }), { reason: "renovation", note: null, affects: [held.id] });
    const user = await signIn("coordinator", "Event requests");
    await user.click(await screen.findByRole("button", { name: /Alumni Night/ }));

    const row = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(row).toHaveTextContent("Needs rearrangement");
    expect(row).toHaveTextContent(/the venue is unavailable from .* \(Safety\): Ceiling inspection\. Find a\s?replacement venue, or withdraw it\./);
    expect(within(row).getByRole("button", { name: "Withdraw" })).toBeInTheDocument();

    const hold = await bookings().findByRole("listitem", { name: /^Hall B/ });
    expect(hold).toHaveTextContent("Needs rearrangement");
    expect(within(hold).queryByRole("button", { name: "Confirm hold" })).not.toBeInTheDocument();
    expect(within(hold).getByRole("button", { name: "Decline hold" })).toBeInTheDocument();
  });

  it("TC-US23A-18: the calendar names the reason a venue is unavailable (AC 6)", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-18T04:00:00Z"));
    onTestFinished(() => {
      vi.useRealTimers();
    });
    const venue = seedVenue({ name: "Hall A" });
    // Fri 20 Nov, 13:00–15:00 Singapore: in the week the calendar opens on.
    seedBlock(venue, { reason: "renovation", note: null });
    const user = await signIn("venue_staff", "Venues");
    const calendar = within(await screen.findByRole("region", { name: "Availability calendar" }));

    await user.selectOptions(await calendar.findByLabelText("Venue"), venue.id);
    await user.click(await calendar.findByRole("button", { name: /^Unavailable: Renovation, 1:00 PM – 3:00 PM/ }));

    const details = within(await screen.findByRole("dialog"));
    expect(details.getByText("Reason")).toBeInTheDocument();
    expect(details.getByText("Renovation")).toBeInTheDocument();
  });

  it("TC-US23A-19: the body is sent in Singapore time and an end before the start is caught (AC 1, 2)", () => {
    const form = {
      venueId: "venue-1",
      startDate: "2026-11-20",
      startTime: "09:00",
      endDate: "2026-11-21",
      endTime: "18:00",
      reason: "maintenance",
      note: "   ",
    };
    expect(toBlockBody(form)).toEqual({
      starts_at: "2026-11-20T09:00:00+08:00",
      ends_at: "2026-11-21T18:00:00+08:00",
      reason: "maintenance",
    });
    expect(endBeforeStart(form)).toBe(false);
    expect(endBeforeStart({ ...form, endDate: "2026-11-20", endTime: "09:00" })).toBe(true);
    expect(toBlockBody({ ...form, startDate: "", reason: "" })).toEqual({ ends_at: "2026-11-21T18:00:00+08:00" });
  });
});
