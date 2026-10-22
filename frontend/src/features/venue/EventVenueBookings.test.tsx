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
} as EventRequest;

function booking(overrides: Partial<VenueBooking> = {}): VenueBooking {
  return {
    id: "booking-1",
    event: { id: "event-1", name: "Venue Booking Demo", request_reference: null, status: "approved" },
    venue: { id: "venue-1", name: "Hall A", location: "Building 1", capacity: 40 },
    requested_by_user_id: "coordinator-id",
    starts_at: "2026-11-20T02:00:00Z",
    ends_at: "2026-11-20T04:00:00Z",
    expected_attendees: 30,
    room_layout: "theatre",
    required_facilities: [],
    required_accessibility_features: [],
    special_requirements: null,
    status: "requested",
    created_at: "2026-10-01T02:00:00Z",
    updated_at: "2026-10-01T02:00:00Z",
    withdrawn_at: null,
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

    const approved = row(/^Room B/);
    expect(within(approved).getByText("Approved")).toBeInTheDocument();
    expect(within(approved).queryByRole("button", { name: "Withdraw" })).not.toBeInTheDocument();
    expect(forEvent).toHaveBeenCalledWith("event-1");
  });

  it("says so when nothing is booked yet", async () => {
    forEvent.mockResolvedValue([]);
    render(<EventVenueBookings event={EVENT} />);

    expect(await screen.findByText("No venue requested for this event yet.")).toBeInTheDocument();
  });

  it("withdraws a pending request, which then shows as Withdrawn (TC-US22-21)", async () => {
    const withdraw = vi
      .spyOn(bookingApi, "withdraw")
      .mockResolvedValue(booking({ status: "withdrawn", withdrawn_at: "2026-10-01T03:00:00Z" }));
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();

    await user.click(within(await screen.findByRole("listitem", { name: /^Hall A/ })).getByRole("button", { name: "Withdraw" }));

    expect(withdraw).toHaveBeenCalledWith("booking-1");
    expect(within(row(/^Hall A/)).getByText("Withdrawn")).toBeInTheDocument();
    expect(within(row(/^Hall A/)).queryByRole("button", { name: "Withdraw" })).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Request for Hall A withdrawn.");
  });

  it("explains BOOKING_NOT_PENDING and reloads the list to show the real status", async () => {
    vi.spyOn(bookingApi, "withdraw").mockRejectedValue(new ApiError(409, "BOOKING_NOT_PENDING", [], { status: "approved" }));
    render(<EventVenueBookings event={EVENT} />);
    const user = userEvent.setup();
    await screen.findByRole("listitem", { name: /^Hall A/ });

    forEvent.mockResolvedValue([booking({ status: "approved" })]);
    await user.click(within(row(/^Hall A/)).getByRole("button", { name: "Withdraw" }));

    expect(screen.getByRole("alert")).toHaveTextContent("This booking is no longer pending (it's approved now)");
    expect(await within(row(/^Hall A/)).findByText("Approved")).toBeInTheDocument();
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
    expect(notice).toHaveTextContent("Venue requested: Hall A, Fri, Nov 20, 2:00 PM – 4:00 PM. Venue staff have been notified.");
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
