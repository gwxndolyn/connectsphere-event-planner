import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { EventRequest } from "../eventRequest/types";
import { venueApi } from "./api";
import { bookingApi } from "./bookingApi";
import type { EventVenues, VenueBooking, VenueBookingCreated } from "./bookingTypes";
import { EventVenueBookings } from "./EventVenueBookings";

const EVENT = {
  id: "event-1",
  name: "Venue Booking Demo",
  status: "approved",
  expected_attendees: 40,
  preferred_dates: ["2026-11-20"],
  preferred_start_time: "14:00:00",
  preferred_end_time: "16:00:00",
  request_reference: null,
  // Assigned to the coordinator the tests act as: only they may book it (US10a, D20).
  coordinator: { id: "coordinator-id", name: "Casey Tan" },
} as EventRequest;

function booking(overrides: Partial<VenueBooking> = {}): VenueBooking {
  return {
    id: "booking-1",
    reference: "VB-2026-000001",
    event: { id: "event-1", name: "Venue Booking Demo", request_reference: null, status: "approved" },
    venue: { id: "venue-1", name: "Hall A", location: "Building 1", capacity: 40 },
    requested_by_user_id: "coordinator-id",
    starts_at: "2026-11-20T02:00:00Z",
    ends_at: "2026-11-20T04:00:00Z",
    // US13: Hall A's 30 min setup and 15 min turnaround.
    occupied_starts_at: "2026-11-20T01:30:00Z",
    occupied_ends_at: "2026-11-20T04:15:00Z",
    expected_attendees: 30,
    room_layout: "theatre",
    required_facilities: [],
    required_accessibility_features: [],
    special_requirements: null,
    status: "requested",
    created_at: "2026-10-01T02:00:00Z",
    updated_at: "2026-10-01T02:00:00Z",
    withdrawn_at: null,
    decided_at: null,
    decided_by_user_id: null,
    rejection_reason: null,
    alternative_suggestion: null,
    purpose: "Main venue",
    is_primary: true,
    preparation_status: "not_started",
    ...overrides,
  };
}

/** The event's bookings as GET /events/{id}/venue-bookings gives them (US24), summary worked out as the API does. */
function venues(list: VenueBooking[], overrides: Partial<EventVenues> = {}): EventVenues {
  const live = list.filter((b) => b.status === "requested" || b.status === "approved");
  const primary = live.find((b) => b.is_primary) ?? null;
  const allocated = live.reduce((sum, b) => sum + b.expected_attendees, 0);
  return {
    bookings: list.map((b) => ({
      ...b,
      unavailability:
        b.status === "rejected"
          ? { kind: "rejected" as const, reason: b.rejection_reason, alternative_suggestion: b.alternative_suggestion }
          : null,
      next_action:
        b.status === "requested" ? "venue_staff_to_decide" : b.status === "rejected" ? "coordinator_to_rebook" : "none",
    })),
    venues_arranged:
      live.length > 0 && live.every((b) => b.status === "approved") && primary !== null && allocated >= 40,
    primary_booking_id: primary?.id ?? null,
    allocated_attendees: allocated,
    expected_attendees: 40,
    next_action: live.length > 0 && primary === null ? "choose_primary" : null,
    ...overrides,
  };
}

let forEvent: ReturnType<typeof vi.spyOn>;

/** What the next read of the event's venues returns. */
function serve(list: VenueBooking[], overrides: Partial<EventVenues> = {}) {
  forEvent.mockResolvedValue(venues(list, overrides));
}

const ROOM_B = { id: "venue-2", name: "Room B", location: "Building 2", capacity: 12 };

beforeEach(() => {
  forEvent = vi.spyOn(bookingApi, "eventVenues");
  serve([booking(), booking({ id: "booking-2", venue: ROOM_B, status: "approved", is_primary: false, purpose: "Breakout A" })]);
  vi.spyOn(venueApi, "list").mockResolvedValue([]);
});

function row(name: RegExp) {
  return screen.getByRole("listitem", { name });
}

describe("EventVenueBookings (US22, SCRUM-113)", () => {
  it("lists the event's bookings with their status; Requested and Approved ones can be withdrawn (AC 4, 5; US24 D69)", async () => {
    render(<EventVenueBookings event={EVENT} />);

    const requested = await screen.findByRole("listitem", { name: /^Hall A/ });
    expect(requested).toHaveAccessibleName("Hall A, Fri, Nov 20, 10:00 AM – 12:00 PM");
    expect(within(requested).getByText("Requested")).toBeInTheDocument();
    expect(within(requested).getByRole("button", { name: "Withdraw" })).toBeInTheDocument();
    // US13 (SCRUM-116): the reference and the window setup and turnaround occupy.
    expect(requested).toHaveTextContent("VB-2026-000001 · Occupied 9:30 AM – 12:15 PM with setup and turnaround");

    const approved = row(/^Room B/);
    expect(within(approved).getByText("Approved")).toBeInTheDocument();
    expect(within(approved).getByRole("button", { name: "Withdraw" })).toBeInTheDocument();
    expect(forEvent).toHaveBeenCalledWith("event-1");
  });

  it("on an unassigned event, says no venue can be requested and offers no button (D20)", async () => {
    render(<EventVenueBookings event={{ ...EVENT, coordinator: null }} />);

    expect(
      screen.getByText(
        "No coordinator is assigned to this event yet, so no venue can be requested for it. A Coordinator Lead assigns one.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request venue" })).not.toBeInTheDocument();
    expect(forEvent).not.toHaveBeenCalled();
  });

  it("on someone else's event, names the assigned coordinator instead of a Request venue button (D20)", async () => {
    // The API answers a coordinator who isn't assigned with 404 (TC-US22-06).
    forEvent.mockRejectedValue(new ApiError(404, "NOT_FOUND"));
    render(<EventVenueBookings event={{ ...EVENT, coordinator: { id: "someone-else", name: "Pat Lim" } }} />);

    expect(
      await screen.findByText("Only Pat Lim, the coordinator assigned to this event, can request a venue for it."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request venue" })).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a rejection's reason and suggested alternative, and still offers Request venue (TC-US4-05, 08)", async () => {
    serve([
      booking({ status: "rejected", rejection_reason: "Being repainted", alternative_suggestion: "Room B is free then" }),
    ]);
    render(<EventVenueBookings event={EVENT} />);

    const rejected = await screen.findByRole("listitem", { name: /^Hall A/ });
    expect(within(rejected).getByText("Rejected")).toBeInTheDocument();
    expect(rejected).toHaveTextContent("Reason: Being repainted");
    expect(rejected).toHaveTextContent("Suggested instead: Room B is free then");
    expect(within(rejected).queryByRole("button", { name: "Withdraw" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Request venue" })).toBeInTheDocument();
  });

  it("says so when nothing is booked yet", async () => {
    serve([]);
    render(<EventVenueBookings event={EVENT} />);

    expect(await screen.findByText("No venue requested for this event yet.")).toBeInTheDocument();
  });

  it("asks before withdrawing, explaining the window is freed at once (TC-US22-21, PR #69 review)", async () => {
    const withdraw = vi.spyOn(bookingApi, "withdraw");
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();

    await user.click(within(await screen.findByRole("listitem", { name: /^Hall A/ })).getByRole("button", { name: "Withdraw" }));

    const dialog = screen.getByRole("dialog", { name: "Withdraw this venue request?" });
    expect(dialog).toHaveTextContent("Hall A · Fri, Nov 20, 10:00 AM – 12:00 PM");
    expect(dialog).toHaveTextContent("The window is released straight away: any coordinator can request Hall A for that time");
    expect(withdraw).not.toHaveBeenCalled();
  });

  it("keeps the request when the coordinator backs out", async () => {
    const withdraw = vi.spyOn(bookingApi, "withdraw");
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();

    await user.click(within(await screen.findByRole("listitem", { name: /^Hall A/ })).getByRole("button", { name: "Withdraw" }));
    await user.click(screen.getByRole("button", { name: "Keep request" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(withdraw).not.toHaveBeenCalled();
    expect(within(row(/^Hall A/)).getByText("Requested")).toBeInTheDocument();
  });

  it("withdraws once confirmed, and the request then shows as Withdrawn (TC-US22-21)", async () => {
    const withdraw = vi
      .spyOn(bookingApi, "withdraw")
      .mockResolvedValue(booking({ status: "withdrawn", withdrawn_at: "2026-10-01T03:00:00Z" }));
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();

    await user.click(within(await screen.findByRole("listitem", { name: /^Hall A/ })).getByRole("button", { name: "Withdraw" }));
    // US24: the panel reads the event's venues again afterwards, for the summary.
    serve([
      booking({ status: "withdrawn", withdrawn_at: "2026-10-01T03:00:00Z" }),
      booking({ id: "booking-2", venue: ROOM_B, status: "approved", is_primary: false, purpose: "Breakout A" }),
    ]);
    await user.click(screen.getByRole("button", { name: "Withdraw request" }));

    expect(withdraw).toHaveBeenCalledWith("booking-1");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(within(row(/^Hall A/)).getByText("Withdrawn")).toBeInTheDocument();
    expect(within(row(/^Hall A/)).queryByRole("button", { name: "Withdraw" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Request for Hall A withdrawn.");
  });

  it("explains BOOKING_NOT_LIVE in the dialog and reloads the list to show the real status", async () => {
    vi.spyOn(bookingApi, "withdraw").mockRejectedValue(new ApiError(409, "BOOKING_NOT_LIVE", [], { status: "rejected" }));
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();
    await screen.findByRole("listitem", { name: /^Hall A/ });

    // Venue staff rejected it meanwhile.
    serve([booking({ status: "rejected" })]);
    await user.click(within(row(/^Hall A/)).getByRole("button", { name: "Withdraw" }));
    await user.click(screen.getByRole("button", { name: "Withdraw request" }));

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("alert")).toHaveTextContent("This booking can't be withdrawn: it's rejected now.");
    // Nothing left to confirm: only the way back.
    expect(within(dialog).queryByRole("button", { name: "Withdraw request" })).not.toBeInTheDocument();
    expect(await within(row(/^Hall A/)).findByText("Rejected")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Back to bookings" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the request form, then shows the booking and the API's warnings (TC-US22-19, 20)", async () => {
    serve([]);
    vi.spyOn(venueApi, "list").mockResolvedValue([
      {
        id: "venue-1",
        name: "Hall A",
        location: "Building 1",
        capacity: 40,
        facilities: [],
        accessibility_features: [],
        room_layouts: ["theatre"],
        opens_at: "08:00:00",
        closes_at: "22:00:00",
        setup_minutes: 0,
        turnaround_minutes: 0,
        is_active: true,
      },
    ]);
    const created: VenueBookingCreated = {
      ...booking({ starts_at: "2026-11-20T06:00:00Z", ends_at: "2026-11-20T08:00:00Z" }),
      warnings: [{ field: "room_layout", item: "classroom", message: "This venue doesn't offer the classroom layout." }],
    };
    vi.spyOn(bookingApi, "create").mockResolvedValue(created);
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Request venue" }));
    await screen.findByRole("option", { name: "Hall A (capacity 40)" });
    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    await user.selectOptions(screen.getByLabelText("Layout"), "classroom");
    serve([created]);
    await user.click(screen.getByRole("button", { name: "Send request" }));

    const notice = await screen.findByRole("status");
    expect(notice).toHaveTextContent("Venue requested: Hall A, Fri, Nov 20, 2:00 PM – 4:00 PM (VB-2026-000001). Venue staff have been notified.");
    expect(within(notice).getByRole("list", { name: "Warnings from the booking" })).toHaveTextContent(
      "This venue doesn't offer the classroom layout.",
    );
    expect(await screen.findByRole("listitem", { name: /^Hall A/ })).toHaveTextContent("Requested");
    expect(screen.queryByRole("button", { name: "Send request" })).not.toBeInTheDocument();
  });

  it("goes back to the list when the form is cancelled", async () => {
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Request venue" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(await screen.findByRole("listitem", { name: /^Hall A/ })).toBeInTheDocument();
  });
});

describe("EventVenueBookings with several venues (US24)", () => {
  it("TC-US24-21: shows each venue's purpose, allocation, status, preparation and the Primary badge", async () => {
    serve([
      booking({ status: "approved", preparation_status: "in_progress" }),
      booking({ id: "booking-2", venue: ROOM_B, purpose: "Breakout A", is_primary: false, expected_attendees: 10 }),
    ]);
    render(<EventVenueBookings event={EVENT} />);

    const main = await screen.findByRole("listitem", { name: /^Hall A/ });
    expect(main).toHaveTextContent("Main venue");
    expect(within(main).getByText("Primary")).toBeInTheDocument();
    expect(main).toHaveTextContent("30 attending");
    // TC-US24-29: preparation is shown, read-only, on an approved venue.
    expect(main).toHaveTextContent("Preparation: In progress");
    expect(within(main).queryByRole("combobox")).not.toBeInTheDocument();

    const breakout = row(/^Room B/);
    expect(breakout).toHaveTextContent("Breakout A");
    expect(within(breakout).queryByText("Primary")).not.toBeInTheDocument();
    // Not approved yet, so nothing to prepare.
    expect(breakout).not.toHaveTextContent("Preparation");
  });

  it("TC-US24-21: totals the allocations against expected attendance and says what's missing", async () => {
    serve([
      booking({ status: "approved", expected_attendees: 25 }),
      booking({ id: "booking-2", venue: ROOM_B, is_primary: false, expected_attendees: 10 }),
    ]);
    render(<EventVenueBookings event={EVENT} />);

    const summary = await screen.findByRole("region", { name: "Venue arrangements" });
    expect(summary).toHaveTextContent("Allocated 35 of 40 expected, short by 5");
    expect(summary).toHaveTextContent("Venues not arranged");
    const missing = within(summary).getByRole("list", { name: "What's missing" });
    expect(missing).toHaveTextContent("1 waiting for Venue staff");
    expect(missing).toHaveTextContent("5 more attendees to allocate");
  });

  it("TC-US24-21: says the venues are arranged when every live venue is approved with a primary and enough room", async () => {
    serve([booking({ status: "approved", expected_attendees: 40 })]);
    render(<EventVenueBookings event={EVENT} />);

    const summary = await screen.findByRole("region", { name: "Venue arrangements" });
    expect(summary).toHaveTextContent("Allocated 40 of 40 expected");
    expect(summary).toHaveTextContent("Venues arranged");
    expect(within(summary).queryByRole("list", { name: "What's missing" })).not.toBeInTheDocument();
  });

  it("TC-US24-22: Make primary moves the badge and reloads", async () => {
    const makePrimary = vi.spyOn(bookingApi, "makePrimary").mockResolvedValue(booking({ id: "booking-2" }));
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();
    await screen.findByRole("listitem", { name: /^Hall A/ });
    // The primary can't be made primary again.
    expect(within(row(/^Hall A/)).queryByRole("button", { name: "Make primary" })).not.toBeInTheDocument();

    serve([booking({ is_primary: false }), booking({ id: "booking-2", venue: ROOM_B, status: "approved", is_primary: true })]);
    await user.click(within(row(/^Room B/)).getByRole("button", { name: "Make primary" }));

    expect(makePrimary).toHaveBeenCalledWith("booking-2");
    expect(await within(row(/^Room B/)).findByText("Primary")).toBeInTheDocument();
    expect(within(row(/^Hall A/)).queryByText("Primary")).not.toBeInTheDocument();
  });

  it("TC-US24-22: a Requested new primary reaches attendees once Venue staff approve it (D70)", async () => {
    serve([booking({ status: "approved" }), booking({ id: "booking-2", venue: ROOM_B, status: "requested", is_primary: false })]);
    vi.spyOn(bookingApi, "makePrimary").mockResolvedValue(
      booking({ id: "booking-2", venue: ROOM_B, status: "requested", is_primary: true }),
    );
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();
    await screen.findByRole("listitem", { name: /^Room B/ });

    await user.click(within(row(/^Room B/)).getByRole("button", { name: "Make primary" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Room B is now the primary venue. Attendees see it once Venue staff have approved it.",
    );
  });

  it("TC-US24-22: an Approved new primary reaches attendees now (D70)", async () => {
    vi.spyOn(bookingApi, "makePrimary").mockResolvedValue(
      booking({ id: "booking-2", venue: ROOM_B, status: "approved", is_primary: true }),
    );
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();
    await screen.findByRole("listitem", { name: /^Room B/ });

    await user.click(within(row(/^Room B/)).getByRole("button", { name: "Make primary" }));

    const notice = await screen.findByRole("status");
    expect(notice).toHaveTextContent("Room B is now the primary venue. Attendees see it now.");
    expect(notice).not.toHaveTextContent("once Venue staff have approved it");
  });

  it("TC-US24-22: asks the coordinator to choose a primary venue when there's none", async () => {
    serve([booking({ is_primary: false }), booking({ id: "booking-2", venue: ROOM_B, status: "approved", is_primary: false })]);
    render(<EventVenueBookings event={EVENT} />);

    const summary = await screen.findByRole("region", { name: "Venue arrangements" });
    expect(within(summary).getByRole("list", { name: "What's missing" })).toHaveTextContent(
      "Choose a primary venue: attendees see none until you do",
    );
    expect(within(row(/^Hall A/)).getByRole("button", { name: "Make primary" })).toBeInTheDocument();
  });

  it("TC-US24-22: shows the API's refusal when a venue can't be made primary", async () => {
    vi.spyOn(bookingApi, "makePrimary").mockRejectedValue(new ApiError(409, "BOOKING_NOT_LIVE", [], { status: "rejected" }));
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();
    await screen.findByRole("listitem", { name: /^Room B/ });

    await user.click(within(row(/^Room B/)).getByRole("button", { name: "Make primary" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This venue can't be the primary one: it's rejected now.");
  });

  it("TC-US24-23: withdrawing an approved venue asks first, says Venue staff will be told, and keeps the others", async () => {
    const withdraw = vi
      .spyOn(bookingApi, "withdraw")
      .mockResolvedValue(booking({ id: "booking-2", venue: ROOM_B, status: "withdrawn", is_primary: false }));
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();
    await screen.findByRole("listitem", { name: /^Room B/ });

    await user.click(within(row(/^Room B/)).getByRole("button", { name: "Withdraw" }));
    const dialog = screen.getByRole("dialog", { name: "Withdraw this approved venue?" });
    expect(dialog).toHaveTextContent("Venue staff will be told");
    expect(dialog).toHaveTextContent("The event's other venues stay as they are.");
    expect(withdraw).not.toHaveBeenCalled();

    serve([booking(), booking({ id: "booking-2", venue: ROOM_B, status: "withdrawn", is_primary: false })]);
    await user.click(within(dialog).getByRole("button", { name: "Withdraw venue" }));

    expect(withdraw).toHaveBeenCalledWith("booking-2");
    expect(await within(row(/^Room B/)).findByText("Withdrawn")).toBeInTheDocument();
    expect(within(row(/^Hall A/)).getByText("Requested")).toBeInTheDocument();
  });
});
