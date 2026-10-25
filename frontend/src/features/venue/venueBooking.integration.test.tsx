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
  setEvaluation,
  startMockBackend,
  VENUE_STAFF_ID,
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

  it("doesn't list an approved event assigned to someone else, so it can't be booked (D20, D48)", async () => {
    seedRequest({ status: "approved", name: "Someone Else's Event", coordinator: { id: "other-coordinator", name: "Pat Lim" } });
    seedRequest({ status: "approved", name: "Venue Booking Demo", ...MINE });
    const user = userEvent.setup();
    await openRequest(user, "Venue Booking Demo");
    await user.click(screen.getByRole("button", { name: "Back to review queue" }));

    expect(screen.queryByRole("button", { name: /Someone Else's Event/ })).not.toBeInTheDocument();
    expect(callsTo("POST", "/api/v1/venue-bookings")).toHaveLength(0);
  });

  it("offers no venue booking on a request that isn't approved (AC 1)", async () => {
    seedRequest({ status: "under_review", name: "Still Under Review", ...MINE });
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

  it("Venue staff approve one request and reject another; the coordinator sees both decisions (TC-US4-02, 04, 05)", async () => {
    const request = seedRequest({ status: "approved", name: "Venue Booking Demo", ...MINE });
    seedBooking(request, seedVenue({ name: "Hall A" }), { created_at: "2026-10-01T01:00:00Z" });
    seedBooking(request, seedVenue({ name: "Hall B" }), { starts_at: "2026-11-21T02:00:00Z", ends_at: "2026-11-21T04:00:00Z" });
    setDevRole("venue_staff");
    const user = userEvent.setup();
    const { unmount } = render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Venues" }));

    const pending = await screen.findByRole("list", { name: "Pending venue requests" });
    await user.click(within(within(pending).getByRole("listitem", { name: "Venue Booking Demo at Hall A" })).getByRole("button", { name: "Approve" }));
    expect(await screen.findByText(/Approved: Hall A is reserved for Venue Booking Demo/)).toBeInTheDocument();

    await user.click(within(screen.getByRole("listitem", { name: "Venue Booking Demo at Hall B" })).getByRole("button", { name: "Reject" }));
    const dialog = screen.getByRole("dialog", { name: "Reject this venue request?" });
    await user.type(within(dialog).getByLabelText("Reason (optional)"), "Closed for maintenance");
    await user.type(within(dialog).getByLabelText("Suggested alternative (optional)"), "Hall A on Saturday");
    await user.click(within(dialog).getByRole("button", { name: "Reject request" }));
    expect(await screen.findByText("No venue requests are waiting for review.")).toBeInTheDocument();

    const [rejected] = callsTo("POST", /\/reject$/);
    expect(rejected.headers.get("X-User-Id")).toBe("venue-staff-id");
    expect(rejected.body).toEqual({ reason: "Closed for maintenance", alternative_suggestion: "Hall A on Saturday" });
    expect(callsTo("POST", /\/approve$/)).toHaveLength(1);

    // The coordinator sees Approved and Rejected, with the notes, and can request again (AC 8).
    unmount();
    const user2 = userEvent.setup();
    await openRequest(user2, "Venue Booking Demo");
    expect(await bookings().findByRole("listitem", { name: /^Hall A/ })).toHaveTextContent("Approved");
    const hallB = bookings().getByRole("listitem", { name: /^Hall B/ });
    expect(hallB).toHaveTextContent("Rejected");
    expect(hallB).toHaveTextContent("Reason: Closed for maintenance");
    expect(hallB).toHaveTextContent("Suggested instead: Hall A on Saturday");
    expect(bookings().getByRole("button", { name: "Request venue" })).toBeInTheDocument();
  });
});

describe("no one decides their own request (US16b D51, SCRUM-121)", () => {
  it("Approve or Reject on a request Venue staff made says who must decide it, and the row stays (TC-US16B-30)", async () => {
    // A Venue staff member who is also a Coordinator requested this one (D51 refuses it on the API).
    const request = seedRequest({ status: "approved", name: "Venue Booking Demo", ...MINE });
    seedBooking(request, seedVenue({ name: "Hall A" }), { requested_by_user_id: VENUE_STAFF_ID });
    setDevRole("venue_staff");
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Venues" }));
    const row = () => screen.getByRole("listitem", { name: "Venue Booking Demo at Hall A" });
    await screen.findByRole("list", { name: "Pending venue requests" });

    await user.click(within(row()).getByRole("button", { name: "Approve" }));
    expect(await within(row()).findByRole("alert")).toHaveTextContent(
      "Another Venue staff member must decide this request, because you made it or coordinate its event.",
    );

    await user.click(within(row()).getByRole("button", { name: "Reject" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Reject request" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(await within(row()).findByRole("alert")).toHaveTextContent("Another Venue staff member must decide this request");
    expect(callsTo("POST", /\/(approve|reject)$/)).toHaveLength(2);
  });
});

describe("venue buffers (US13, SCRUM-116)", () => {
  it("Venue staff see each pending request's occupied window, reference and conflicts from the evaluation (TC-US13-18)", async () => {
    const request = seedRequest({ status: "approved", name: "Venue Booking Demo", ...MINE });
    const hall = seedVenue({ name: "Hall A", setup_minutes: 30, turnaround_minutes: 15 });
    const clashing = seedBooking(request, hall);
    setEvaluation(clashing, {
      conflicts: [
        {
          kind: "block",
          reference: null,
          note: "Repainting",
          starts_at: "2026-11-20T03:00:00Z",
          ends_at: "2026-11-20T06:00:00Z",
          occupied: { starts_at: "2026-11-20T03:00:00Z", ends_at: "2026-11-20T06:00:00Z" },
          overlap: { starts_at: "2026-11-20T03:00:00Z", ends_at: "2026-11-20T04:15:00Z" },
        },
      ],
    });
    seedBooking(request, seedVenue({ name: "Hall B" }), { starts_at: "2026-11-21T02:00:00Z", ends_at: "2026-11-21T04:00:00Z" });
    setDevRole("venue_staff");
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Venues" }));

    const pending = await screen.findByRole("list", { name: "Pending venue requests" });
    const hallA = within(pending).getByRole("listitem", { name: "Venue Booking Demo at Hall A" });
    expect(hallA).toHaveTextContent("VB-2026-000001 · Occupied 9:30 AM – 12:15 PM with setup and turnaround");
    expect(await within(hallA).findByRole("list", { name: "Conflicts" })).toHaveTextContent(
      "Venue closure (Repainting), Fri, Nov 20, 11:00 AM – 2:00 PM: overlap 11:00 AM – 12:15 PM",
    );
    const hallB = within(pending).getByRole("listitem", { name: "Venue Booking Demo at Hall B" });
    expect(await within(hallB).findByText("No conflicts with setup and turnaround.")).toBeInTheDocument();

    const checks = callsTo("GET", /\/evaluation$/);
    expect(checks).toHaveLength(2);
    expect(checks.every((call) => call.headers.get("X-User-Id") === "venue-staff-id")).toBe(true);
  });

  it("the coordinator sees the occupied window before sending and the reference after (TC-US13-16)", async () => {
    seedRequest({ status: "approved", name: "Venue Booking Demo", expected_attendees: 40, ...MINE });
    const venue = seedVenue({ name: "Hall A", room_layouts: ["theatre"], setup_minutes: 30, turnaround_minutes: 45 });
    const user = userEvent.setup();
    await openRequest(user, "Venue Booking Demo");

    await user.click(await bookings().findByRole("button", { name: "Request venue" }));
    await user.selectOptions(await screen.findByLabelText("Venue"), venue.id);
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.clear(screen.getByLabelText("Start time"));
    await user.type(screen.getByLabelText("Start time"), "10:00");
    await user.clear(screen.getByLabelText("End time"));
    await user.type(screen.getByLabelText("End time"), "12:00");
    expect(screen.getByText(/^The venue is occupied 9:30 AM – 12:45 PM \(30 min setup, 45 min turnaround\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(await screen.findByText(/Venue requested: Hall A, Fri, Nov 20, 10:00 AM – 12:00 PM \(VB-2026-000001\)/)).toBeInTheDocument();
    expect(await bookings().findByRole("listitem", { name: /^Hall A/ })).toHaveTextContent(
      "VB-2026-000001 · Occupied 9:30 AM – 12:45 PM with setup and turnaround",
    );
  });
});
