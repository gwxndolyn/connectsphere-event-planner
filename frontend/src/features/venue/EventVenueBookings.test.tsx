import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { EventRequest } from "../eventRequest/types";
import { venueApi } from "./api";
import { bookingApi } from "./bookingApi";
import type { VenueBooking, VenueBookingCreated } from "./bookingTypes";
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

let forEvent: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  forEvent = vi.spyOn(bookingApi, "forEvent").mockResolvedValue([
    booking(),
    booking({ id: "booking-2", venue: { id: "venue-2", name: "Room B", location: "Building 2", capacity: 12 }, status: "approved" }),
  ]);
  vi.spyOn(venueApi, "list").mockResolvedValue([]);
});

function row(name: RegExp) {
  return screen.getByRole("listitem", { name });
}

describe("EventVenueBookings (US22, SCRUM-113)", () => {
  it("lists the event's bookings with their status; only a Requested one can be withdrawn (AC 4, 5)", async () => {
    render(<EventVenueBookings event={EVENT} />);

    const requested = await screen.findByRole("listitem", { name: /^Hall A/ });
    expect(requested).toHaveAccessibleName("Hall A, Fri, Nov 20, 10:00 AM – 12:00 PM");
    expect(within(requested).getByText("Requested")).toBeInTheDocument();
    expect(within(requested).getByRole("button", { name: "Withdraw" })).toBeInTheDocument();
    // US13 (SCRUM-116): the reference and the window setup and turnaround occupy.
    expect(requested).toHaveTextContent("VB-2026-000001 · Occupied 9:30 AM – 12:15 PM with setup and turnaround");

    const approved = row(/^Room B/);
    expect(within(approved).getByText("Approved")).toBeInTheDocument();
    expect(within(approved).queryByRole("button", { name: "Withdraw" })).not.toBeInTheDocument();
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
    forEvent.mockResolvedValue([
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
    forEvent.mockResolvedValue([]);
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
    forEvent.mockResolvedValue([booking({ status: "rejected" })]);
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
    forEvent.mockResolvedValue([]);
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
    forEvent.mockResolvedValue([created]);
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
