import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import {
  callsTo,
  COORDINATOR_PERSON,
  seedBooking,
  seedRequest,
  seedVenue,
  server,
  startMockBackend,
} from "../../test/server";

// US22 (SCRUM-89, PR 3 SCRUM-113): the real App, review queue and booking screens against the fake
// backend. Whether a window is free, the capacity rule and the venue warnings are the API's rules,
// tested in backend/tests/venue/test_booking_api.py and e2e/tests/venue-booking.spec.ts; these tests
// check what the screens send and show.
startMockBackend();

type User = ReturnType<typeof userEvent.setup>;

// Only the event's assigned coordinator may book it (US10a, D20), so the flows' events are assigned
// to the coordinator the tests act as.
const MINE = { coordinator: { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name } };

async function openRequest(user: User, name: string) {
  setDevRole("coordinator");
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
  await screen.findByRole("heading", { name: "Review request" });
}

function bookings() {
  return within(screen.getByRole("region", { name: "Venue bookings" }));
}

describe("venue booking (US22)", () => {
  it("a coordinator requests a venue for an approved event, which then shows as Requested (TC-US22-19)", async () => {
    seedRequest({ status: "approved", name: "Venue Booking Demo", expected_attendees: 40, ...MINE });
    const venue = seedVenue({ name: "Hall A", room_layouts: ["theatre"] });
    const user = userEvent.setup();
    await openRequest(user, "Venue Booking Demo");

    expect(await bookings().findByText("No venue requested for this event yet.")).toBeInTheDocument();
    await user.click(bookings().getByRole("button", { name: "Request venue" }));
    await user.selectOptions(await screen.findByLabelText("Venue"), venue.id);
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.clear(screen.getByLabelText("Start time"));
    await user.type(screen.getByLabelText("Start time"), "10:00");
    await user.clear(screen.getByLabelText("End time"));
    await user.type(screen.getByLabelText("End time"), "12:00");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(await screen.findByText(/Venue requested: Hall A, Fri, Nov 20, 10:00 AM – 12:00 PM/)).toBeInTheDocument();
    expect(await bookings().findByRole("listitem", { name: /^Hall A/ })).toHaveTextContent("Requested");

    const [sent] = callsTo("POST", "/api/v1/venue-bookings");
    expect(sent.headers.get("X-User-Id")).toBe("coordinator-id");
    expect(sent.body).toMatchObject({
      venue_id: venue.id,
      starts_at: "2026-11-20T10:00:00+08:00",
      ends_at: "2026-11-20T12:00:00+08:00",
      expected_attendees: 40,
      room_layout: "theatre",
    });
  });

  it("shows the API's capacity error on attendance (TC-US22-20)", async () => {
    seedRequest({ status: "approved", name: "Venue Booking Demo", ...MINE });
    const venue = seedVenue({ name: "Hall A", capacity: 12, room_layouts: ["theatre"] });
    server.use(
      http.post("http://api.test/api/v1/venue-bookings", () =>
        HttpResponse.json(
          {
            code: "VENUE_CAPACITY_EXCEEDED",
            fields: ["expected_attendees"],
            capacity: 12,
            message: "Expected attendance is more than this venue's capacity of 12.",
          },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    await openRequest(user, "Venue Booking Demo");

    await user.click(await bookings().findByRole("button", { name: "Request venue" }));
    await user.selectOptions(await screen.findByLabelText("Venue"), venue.id);
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(await screen.findByLabelText("Expected attendance")).toHaveAccessibleDescription(
      "Expected attendance is more than this venue's capacity of 12.",
    );
  });

  it("withdraws a pending request after confirming (TC-US22-21)", async () => {
    const request = seedRequest({ status: "approved", name: "Venue Booking Demo", ...MINE });
    seedBooking(request, seedVenue({ name: "Hall A" }));
    const user = userEvent.setup();
    await openRequest(user, "Venue Booking Demo");

    const row = await bookings().findByRole("listitem", { name: /^Hall A/ });
    await user.click(within(row).getByRole("button", { name: "Withdraw" }));
    // Nothing is sent until the coordinator confirms.
    expect(callsTo("POST", /\/withdraw$/)).toHaveLength(0);
    await user.click(within(screen.getByRole("dialog", { name: "Withdraw this venue request?" })).getByRole("button", { name: "Withdraw request" }));

    expect(await within(row).findByText("Withdrawn")).toBeInTheDocument();
    expect(callsTo("POST", /\/withdraw$/)).toHaveLength(1);
  });

  it("on an approved event assigned to someone else, names them and offers no Request venue (D20)", async () => {
    seedRequest({ status: "approved", name: "Someone Else's Event", coordinator: { id: "other-coordinator", name: "Pat Lim" } });
    const user = userEvent.setup();
    await openRequest(user, "Someone Else's Event");

    expect(
      await bookings().findByText("Only Pat Lim, the coordinator assigned to this event, can request a venue for it."),
    ).toBeInTheDocument();
    expect(bookings().queryByRole("button", { name: "Request venue" })).not.toBeInTheDocument();
    expect(callsTo("POST", "/api/v1/venue-bookings")).toHaveLength(0);
  });

  it("offers no venue booking on a request that isn't approved (AC 1)", async () => {
    seedRequest({ status: "under_review", name: "Still Under Review" });
    const user = userEvent.setup();
    await openRequest(user, "Still Under Review");

    expect(screen.queryByRole("region", { name: "Venue bookings" })).not.toBeInTheDocument();
    expect(callsTo("GET", /\/venue-bookings$/)).toHaveLength(0);
  });

  it("Venue staff see the pending list on Venues (AC 4)", async () => {
    const request = seedRequest({ status: "approved", name: "Venue Booking Demo", ...MINE });
    seedBooking(request, seedVenue({ name: "Hall A" }));
    setDevRole("venue_staff");
    const user = userEvent.setup();
    render(<App />);

    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Venues" }));

    const pending = await screen.findByRole("list", { name: "Pending venue requests" });
    expect(within(pending).getByRole("listitem", { name: "Venue Booking Demo at Hall A" })).toHaveTextContent(
      "Fri, Nov 20, 10:00 AM – 12:00 PM",
    );
    expect(callsTo("GET", "/api/v1/venue-bookings/pending")[0].headers.get("X-User-Id")).toBe("venue-staff-id");
  });
});
