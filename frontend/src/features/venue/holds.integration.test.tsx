import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, onTestFinished, vi } from "vitest";
import App from "../../App";
import { setDevRole, type DevRole } from "../../api/client";
import { callsTo, COORDINATOR_PERSON, seedBooking, seedRequest, seedVenue, startMockBackend } from "../../test/server";
import { holdCountdown } from "./bookingApi";

// US25 (SCRUM-93): the real App, Venue staff's Venues screen and the coordinator's review screen against the fake
// backend. The expiry's rules, the conflict check and expiry on read are the API's (backend/tests/venue/
// test_holds.py); these check what the screens send and show.
startMockBackend();

const MINE = { coordinator: { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name } };

async function signIn(role: DevRole, screenName: string) {
  setDevRole(role);
  const user = userEvent.setup();
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: screenName }));
  return user;
}

function holds() {
  return within(screen.getByRole("region", { name: "Hold a venue" }));
}

function bookings() {
  return within(screen.getByRole("region", { name: "Venue bookings" }));
}

describe("tentative venue holds (US25)", () => {
  it("TC-US25-18: Venue staff hold a venue for an event until an expiry (AC 1)", async () => {
    const event = seedRequest({ status: "approved", name: "Alumni Night", expected_attendees: 30, ...MINE });
    const venue = seedVenue({ name: "Hall A", room_layouts: ["theatre"] });
    const user = await signIn("venue_staff", "Venues");

    await user.click(await holds().findByRole("button", { name: "Place a hold" }));
    await user.selectOptions(await holds().findByLabelText("Event"), await holds().findByRole("option", { name: /Alumni Night/ }));
    await user.selectOptions(await holds().findByLabelText("Venue"), venue.id);
    await user.type(holds().getByLabelText("Purpose"), "Main hall");
    await user.selectOptions(holds().getByLabelText("Layout"), "theatre");
    await user.clear(holds().getByLabelText("Start time"));
    await user.type(holds().getByLabelText("Start time"), "10:00");
    await user.clear(holds().getByLabelText("End time"));
    await user.type(holds().getByLabelText("End time"), "12:00");
    await user.type(holds().getByLabelText("Hold expires on"), "2026-11-10");
    await user.click(holds().getByRole("button", { name: "Place hold" }));

    expect(await holds().findByRole("status")).toHaveTextContent(/Held Hall A for Alumni Night until .*The coordinator has been told./);
    const [sent] = callsTo("POST", "/api/v1/venue-holds");
    expect(sent.body).toMatchObject({
      event_id: event.id,
      venue_id: venue.id,
      starts_at: "2026-11-20T10:00:00+08:00",
      ends_at: "2026-11-20T12:00:00+08:00",
      purpose: "Main hall",
      hold_expires_at: "2026-11-10T17:00:00+08:00",
    });
  });

  it("TC-US25-19: no expiry is refused on the expiry field, and nothing is held (AC 1)", async () => {
    seedRequest({ status: "approved", name: "Alumni Night", expected_attendees: 30, ...MINE });
    const venue = seedVenue({ name: "Hall A", room_layouts: ["theatre"] });
    const user = await signIn("venue_staff", "Venues");

    await user.click(await holds().findByRole("button", { name: "Place a hold" }));
    await user.selectOptions(await holds().findByLabelText("Event"), await holds().findByRole("option", { name: /Alumni Night/ }));
    await user.selectOptions(await holds().findByLabelText("Venue"), venue.id);
    await user.type(holds().getByLabelText("Purpose"), "Main hall");
    await user.selectOptions(holds().getByLabelText("Layout"), "theatre");
    await user.click(holds().getByRole("button", { name: "Place hold" }));

    expect(await holds().findByRole("alert")).toHaveTextContent("Complete the fields marked below.");
    expect(holds().getByLabelText("Hold expires on")).toHaveAttribute("aria-invalid", "true");
  });

  it("TC-US25-20: the coordinator sees the hold with its expiry and confirms it into a request (AC 4, 5)", async () => {
    const event = seedRequest({ status: "approved", name: "Alumni Night", ...MINE });
    const venue = seedVenue({ name: "Hall A" });
    const held = seedBooking(event, venue, {
      status: "held",
      is_primary: false,
      requested_by_user_id: "venue-staff-id",
      held_by_user_id: "venue-staff-id",
      hold_expires_at: "2026-11-10T09:00:00Z",
    });
    const user = await signIn("coordinator", "Event requests");
    await user.click(await screen.findByRole("button", { name: /Alumni Night/ }));

    const row = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(row).toHaveTextContent("Held");
    expect(row).toHaveTextContent(/Held for this event until .*Confirm it to request it, or decline it./);
    await user.click(within(row).getByRole("button", { name: "Confirm hold" }));

    expect(await bookings().findByRole("status")).toHaveTextContent(
      /Hold confirmed: Hall A is now a request. Venue staff have been notified and must approve it by/,
    );
    expect(callsTo("POST", `/api/v1/venue-bookings/${held.id}/confirm`)).toHaveLength(1);
    const after = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(after).toHaveTextContent("Requested");
    expect(after).toHaveTextContent(/From a hold: Venue staff must approve it by/);
  });

  it("TC-US25-21: the coordinator declines a hold and the venue is free again (AC 7)", async () => {
    const event = seedRequest({ status: "approved", name: "Alumni Night", ...MINE });
    const venue = seedVenue({ name: "Hall A" });
    const held = seedBooking(event, venue, {
      status: "held",
      is_primary: false,
      requested_by_user_id: "venue-staff-id",
      held_by_user_id: "venue-staff-id",
      hold_expires_at: "2026-11-10T09:00:00Z",
    });
    const user = await signIn("coordinator", "Event requests");
    await user.click(await screen.findByRole("button", { name: /Alumni Night/ }));

    const row = await bookings().findByRole("listitem", { name: /^Hall A/ });
    await user.click(within(row).getByRole("button", { name: "Decline hold" }));
    // It asks first, as Withdraw does: nothing is sent until confirmed, and Keep hold backs out.
    const confirm = within(within(row).getByRole("group", { name: "Confirm declining the hold" }));
    expect(confirm.getByText(/The venue is free for anyone to book at once./)).toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/venue-bookings/${held.id}/withdraw`)).toHaveLength(0);
    await user.click(confirm.getByRole("button", { name: "Decline hold" }));

    expect(await bookings().findByRole("status")).toHaveTextContent("Hold on Hall A declined. The venue is free again.");
    expect(callsTo("POST", `/api/v1/venue-bookings/${held.id}/withdraw`)).toHaveLength(1);
    expect(await bookings().findByRole("listitem", { name: /^Hall A/ })).toHaveTextContent("Withdrawn");
  });

  it("TC-US25-23: the calendar draws a hold, with until when it's held (AC 2)", async () => {
    // The calendar opens on today's week, so fix today to the hold's week, as the US21 tests do.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-10-14T04:00:00Z"));
    onTestFinished(() => {
      vi.useRealTimers();
    });
    const venue = seedVenue({ name: "Hall A" });
    // Tue 13 Oct, 10:00–12:00 Singapore: in the week the calendar opens on.
    seedBooking(seedRequest({ status: "approved", name: "Alumni Night", ...MINE }), venue, {
      status: "held",
      is_primary: false,
      starts_at: "2026-10-13T02:00:00Z",
      ends_at: "2026-10-13T04:00:00Z",
      hold_expires_at: "2026-10-10T09:00:00Z",
      held_by_user_id: "venue-staff-id",
    });
    const user = await signIn("venue_staff", "Venues");
    const calendar = within(await screen.findByRole("region", { name: "Availability calendar" }));

    await user.selectOptions(await calendar.findByLabelText("Venue"), venue.id);
    const item = await calendar.findByRole("button", { name: /^Hold: Alumni Night, 10:00 AM – 12:00 PM/ });
    await user.click(item);

    const details = within(await screen.findByRole("dialog"));
    expect(details.getByText("Held until")).toBeInTheDocument();
    expect(details.getByText("Held")).toBeInTheDocument();
  });

  it("TC-US25-22: a countdown reads the time a hold has left (AC 4)", () => {
    const now = Date.parse("2026-11-01T00:00:00Z");
    expect(holdCountdown("2026-11-04T00:00:00Z", now)).toBe("expires in 3 days");
    expect(holdCountdown("2026-11-01T20:00:00Z", now)).toBe("expires in 20 h");
    expect(holdCountdown("2026-11-01T00:45:00Z", now)).toBe("expires in 45 min");
    expect(holdCountdown("2026-10-31T23:00:00Z", now)).toBe("expiring now");
  });
});
