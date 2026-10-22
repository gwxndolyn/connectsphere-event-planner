import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { bookingApi } from "./bookingApi";
import type { VenueBooking } from "./bookingTypes";
import { PendingBookings } from "./PendingBookings";

function booking(overrides: Partial<VenueBooking> = {}): VenueBooking {
  return {
    id: "booking-1",
    event: { id: "event-1", name: "Venue Booking Demo", request_reference: null, status: "approved" },
    venue: { id: "venue-1", name: "Hall A", location: "Building 1", capacity: 40 },
    requested_by_user_id: "coordinator-id",
    starts_at: "2026-11-20T02:00:00Z",
    ends_at: "2026-11-20T04:00:00Z",
    expected_attendees: 30,
    room_layout: "u_shape",
    required_facilities: ["projector"],
    required_accessibility_features: ["wheelchair"],
    special_requirements: "Lectern at the front",
    status: "requested",
    created_at: "2026-10-01T02:00:00Z",
    updated_at: "2026-10-01T02:00:00Z",
    withdrawn_at: null,
    ...overrides,
  };
}

describe("PendingBookings (US22 AC 4)", () => {
  it("lists each pending request with its event, venue, window and needs", async () => {
    vi.spyOn(bookingApi, "pending").mockResolvedValue([
      booking(),
      booking({ id: "booking-2", event: { id: "event-2", name: null, request_reference: "ER-2026-000042", status: "planning" } }),
    ]);
    render(<PendingBookings />);

    const first = await screen.findByRole("listitem", { name: "Venue Booking Demo at Hall A" });
    expect(first).toHaveTextContent("Fri, Nov 20, 10:00 AM – 12:00 PM");
    expect(first).toHaveTextContent("30 attending");
    expect(first).toHaveTextContent("U-shape");
    expect(first).toHaveTextContent("Projector, Wheelchair");
    expect(first).toHaveTextContent("Lectern at the front");
    // An unnamed request is named by its reference.
    expect(screen.getByRole("listitem", { name: "ER-2026-000042 at Hall A" })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Pending venue requests" })).getAllByRole("listitem")).toHaveLength(2);
  });

  it("says so when nothing is waiting", async () => {
    vi.spyOn(bookingApi, "pending").mockResolvedValue([]);
    render(<PendingBookings />);

    expect(await screen.findByText("No venue requests are waiting for review.")).toBeInTheDocument();
  });

  it("shows why the list couldn't load", async () => {
    vi.spyOn(bookingApi, "pending").mockRejectedValue(new ApiError(403, "FORBIDDEN"));
    render(<PendingBookings />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Only Venue staff can see pending venue requests.");
  });
});
