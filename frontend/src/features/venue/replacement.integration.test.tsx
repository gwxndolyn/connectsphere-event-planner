import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, onTestFinished, vi } from "vitest";
import App from "../../App";
import { setDevRole, type DevRole } from "../../api/client";
import {
  callsTo,
  COORDINATOR_PERSON,
  nextSearchResult,
  seedBlock,
  seedBooking,
  seedRequest,
  seedVenue,
  startMockBackend,
} from "../../test/server";
import { singaporeInstant, singaporeParts } from "./bookingApi";

// US23b (SCRUM-91): the real App, the coordinator's review screen and Venue staff's Venues screen against the fake
// backend. Which venues are free, what a replacement or restore is refused for, and what approving one does are the
// API's (backend/tests/venue/test_replacement.py); these check what the screens send and show.
startMockBackend();

const MINE = { coordinator: { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name } };

async function signIn(role: DevRole, screenName: string) {
  setDevRole(role);
  const user = userEvent.setup();
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: screenName }));
  return user;
}

function bookings() {
  return within(screen.getByRole("region", { name: "Venue bookings" }));
}

/** An approved primary booking of Hall A, 20 Nov 10:00–12:00 Singapore, marked by a maintenance period. */
function markedBooking(blockOverrides: Parameters<typeof seedBlock>[1] = {}) {
  const event = seedRequest({ status: "planning", name: "Alumni Night", ...MINE });
  const hallA = seedVenue({ name: "Hall A" });
  const original = seedBooking(event, hallA, { status: "approved", is_primary: true, expected_attendees: 30 });
  const block = seedBlock(hallA, { reason: "maintenance", note: "Aircon repair", affects: [original.id], ...blockOverrides });
  return { event, hallA, original, block };
}

async function openEvent(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /Alumni Night/ }));
}

describe("replacement venue (US23b)", () => {
  it("TC-US23B-13: the coordinator searches from the notice with the booking's time and attendance, and requests a replacement (AC 1, 2, 3)", async () => {
    const { original } = markedBooking();
    const hallB = seedVenue({ name: "Hall B" });
    nextSearchResult([hallB]);
    const user = await signIn("coordinator", "Event requests");
    await openEvent(user);

    const row = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(row).toHaveTextContent("Needs rearrangement");
    await user.click(within(row).getByRole("button", { name: "Find a replacement" }));

    expect(await screen.findByRole("heading", { name: "Find a replacement venue" })).toBeInTheDocument();
    const [search] = callsTo("GET", "/api/v1/venues/available");
    expect(Object.fromEntries(search.url.searchParams)).toEqual({
      date: "2026-11-20",
      start_time: "10:00",
      end_time: "12:00",
      attendees: "30",
    });
    expect(await screen.findByText(/1 venue is free Fri, Nov 20, 10:00 AM – 12:00 PM for 30 attendees/)).toBeInTheDocument();
    const venueSelect = screen.getByLabelText("Venue", { selector: "select" });
    expect(within(venueSelect).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Choose a venue",
      "Hall B (capacity 40)",
    ]);
    await user.selectOptions(venueSelect, hallB.id);
    await user.click(screen.getByRole("button", { name: "Send request" }));

    const [sent] = callsTo("POST", "/api/v1/venue-bookings");
    expect(sent.body).toMatchObject({
      venue_id: hallB.id,
      starts_at: "2026-11-20T10:00:00+08:00",
      ends_at: "2026-11-20T12:00:00+08:00",
      expected_attendees: 30,
      purpose: "Main venue",
      replaces_booking_id: original.id,
    });
    expect(await screen.findByText(/Replacement requested: Hall B/)).toBeInTheDocument();
    const after = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(after).toHaveTextContent(/Replacement requested: Hall B/);
    expect(within(after).queryByRole("button", { name: "Find a replacement" })).not.toBeInTheDocument();
  });

  it("TC-US23B-14: when nothing is free, the coordinator is told and can search again with other values (AC 2)", async () => {
    markedBooking();
    nextSearchResult([]);
    const user = await signIn("coordinator", "Event requests");
    await openEvent(user);
    await user.click(await bookings().findByRole("button", { name: "Find a replacement" }));

    expect(await screen.findByText(/No venue is free Fri, Nov 20/)).toBeInTheDocument();
    nextSearchResult([seedVenue({ name: "Hall C" })]);
    await user.clear(screen.getByLabelText("Start time"));
    await user.type(screen.getByLabelText("Start time"), "14:00");
    await user.clear(screen.getByLabelText("End time"));
    await user.type(screen.getByLabelText("End time"), "16:00");
    await user.click(screen.getByRole("button", { name: "Search again" }));

    expect(await screen.findByText(/1 venue is free Fri, Nov 20, 2:00 PM – 4:00 PM/)).toBeInTheDocument();
    const searches = callsTo("GET", "/api/v1/venues/available");
    expect(searches.at(-1)?.url.searchParams.get("start_time")).toBe("14:00");
  });

  it("TC-US23B-15: a replaced booking keeps its details and names its replacement (AC 4)", async () => {
    const { event, hallA, original } = markedBooking();
    original.status = "replaced";
    original.replaced_at = "2026-11-03T02:00:00Z";
    const replacement = seedBooking(event, seedVenue({ name: "Hall B" }), {
      status: "approved",
      is_primary: true,
      replaces_booking_id: original.id,
    });
    const user = await signIn("coordinator", "Event requests");
    await openEvent(user);

    const old = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(old).toHaveTextContent("Replaced");
    expect(old).toHaveTextContent(`Replaced by Hall B (${replacement.reference})`);
    expect(old).toHaveTextContent(original.reference);
    expect(old).not.toHaveTextContent("Needs rearrangement");
    expect(within(old).queryByRole("button", { name: "Withdraw" })).not.toBeInTheDocument();
    const now = bookings().getByRole("listitem", { name: /^Hall B/ });
    expect(now).toHaveTextContent(`Replaces ${original.reference} at ${hallA.name}.`);
  });

  it("TC-US23B-16: once Venue staff end the period early, the coordinator asks to restore the booking (AC 5)", async () => {
    const { original } = markedBooking({ ended_early_at: "2026-11-03T01:00:00Z", ends_at: "2026-11-20T01:00:00Z" });
    const user = await signIn("coordinator", "Event requests");
    await openEvent(user);

    const row = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(row).toHaveTextContent(/Venue staff ended that early on/);
    await user.click(within(row).getByRole("button", { name: "Ask to restore" }));

    expect(callsTo("POST", `/api/v1/venue-bookings/${original.id}/restore`)).toHaveLength(1);
    expect(await screen.findByText(/Restore requested: Venue staff have been asked/)).toBeInTheDocument();
    const after = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(after).toHaveTextContent("You asked to restore this booking; Venue staff confirm it.");
    expect(within(after).queryByRole("button", { name: "Ask to restore" })).not.toBeInTheDocument();
  });

  it("TC-US23B-16: after Venue staff decline, the coordinator sees why and can ask again (AC 5)", async () => {
    const { original } = markedBooking({ ended_early_at: "2026-11-03T01:00:00Z" });
    original.restore_declined_at = "2026-11-03T02:00:00Z";
    original.restore_decline_reason = "Still testing the aircon";
    const user = await signIn("coordinator", "Event requests");
    await openEvent(user);

    const row = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(row).toHaveTextContent(/Venue staff declined the restore on .*: Still testing the aircon\. Ask again, or find a replacement\./);
    await user.click(within(row).getByRole("button", { name: "Ask to restore" }));

    const after = await bookings().findByRole("listitem", { name: /^Hall A/ });
    expect(after).toHaveTextContent("You asked to restore this booking; Venue staff confirm it.");
    expect(after).not.toHaveTextContent("declined");
  });

  it("TC-US23B-17: Venue staff confirm one restore request and decline another with a reason (AC 5)", async () => {
    const { original } = markedBooking({ ended_early_at: "2026-11-03T01:00:00Z" });
    original.restore_requested_at = "2026-11-03T01:30:00Z";
    const other = seedRequest({ status: "planning", name: "Careers Fair", ...MINE });
    const hallC = seedVenue({ name: "Hall C" });
    const second = seedBooking(other, hallC, { status: "approved", restore_requested_at: "2026-11-03T01:40:00Z" });
    seedBlock(hallC, { affects: [second.id], ended_early_at: "2026-11-03T01:00:00Z" });
    const user = await signIn("venue_staff", "Venues");

    const section = within(await screen.findByRole("region", { name: /Requests to restore a booking/ }));
    expect(section.getByRole("heading")).toHaveTextContent("Requests to restore a booking (2)");
    await user.click(within(section.getByRole("listitem", { name: "Alumni Night at Hall A" })).getByRole("button", { name: "Confirm restore" }));
    expect(callsTo("POST", `/api/v1/venue-bookings/${original.id}/restore/confirm`)).toHaveLength(1);
    expect(await section.findByRole("status")).toHaveTextContent(`${original.reference} restored`);

    const careers = section.getByRole("listitem", { name: "Careers Fair at Hall C" });
    await user.click(within(careers).getByRole("button", { name: "Decline" }));
    await user.type(within(careers).getByLabelText("Reason (optional)"), "Still testing the aircon");
    await user.click(within(careers).getByRole("button", { name: "Decline restore" }));

    const [declined] = callsTo("POST", `/api/v1/venue-bookings/${second.id}/restore/decline`);
    expect(declined.body).toEqual({ reason: "Still testing the aircon" });
    expect(await section.findByRole("status")).toHaveTextContent(`Restore of ${second.reference} declined`);
  });

  it("TC-US23B-18: Venue staff end a period early from the calendar, after confirming (AC 5)", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-18T04:00:00Z"));
    onTestFinished(() => {
      vi.useRealTimers();
    });
    const { hallA, block } = markedBooking({ starts_at: "2026-11-20T05:00:00Z", ends_at: "2026-11-20T07:00:00Z" });
    const user = await signIn("venue_staff", "Venues");
    const calendar = within(await screen.findByRole("region", { name: "Availability calendar" }));

    await user.selectOptions(await calendar.findByLabelText("Venue"), hallA.id);
    await user.click(await calendar.findByRole("button", { name: /^Unavailable: Aircon repair, 1:00 PM – 3:00 PM/ }));
    const details = within(await screen.findByRole("dialog"));
    await user.click(details.getByRole("button", { name: "End early" }));
    expect(details.getByText("End this period now? The venue is available again from now on.")).toBeInTheDocument();
    await user.click(details.getByRole("button", { name: "End period" }));

    expect(callsTo("POST", `/api/v1/venues/${hallA.id}/blocks/${block.id}/end`)).toHaveLength(1);
    expect(await details.findByRole("status")).toHaveTextContent(
      "Ended early. 1 booking can now be restored once its coordinator asks.",
    );
  });

  it("TC-US23B-19: the form reads a booking's Singapore date and times back from its instants (AC 2)", () => {
    expect(singaporeParts("2026-11-20T02:00:00Z")).toEqual({ date: "2026-11-20", time: "10:00" });
    expect(singaporeParts("2026-11-20T16:30:00Z")).toEqual({ date: "2026-11-21", time: "00:30" });
    const { date, time } = singaporeParts("2026-11-20T09:45:00+08:00");
    expect(singaporeInstant(date, time)).toBe("2026-11-20T09:45:00+08:00");
  });
});
