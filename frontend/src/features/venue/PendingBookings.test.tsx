import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    decided_at: null,
    decided_by_user_id: null,
    rejection_reason: null,
    alternative_suggestion: null,
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

describe("PendingBookings decisions (US4, SCRUM-8)", () => {
  it("approves a request as a whole and takes it off the list (TC-US4-02)", async () => {
    vi.spyOn(bookingApi, "pending").mockResolvedValue([booking()]);
    const approve = vi.spyOn(bookingApi, "approve").mockResolvedValue(booking({ status: "approved" }));
    const user = userEvent.setup();
    render(<PendingBookings />);

    const row = await screen.findByRole("listitem", { name: "Venue Booking Demo at Hall A" });
    await user.click(within(row).getByRole("button", { name: "Approve" }));

    expect(approve).toHaveBeenCalledWith("booking-1");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Approved: Hall A is reserved for Venue Booking Demo, Fri, Nov 20, 10:00 AM – 12:00 PM. The coordinator has been notified.",
    );
    expect(screen.getByText("No venue requests are waiting for review.")).toBeInTheDocument();
  });

  it("explains a refused approval on the row, which stays pending with Reject still offered (TC-US4-03)", async () => {
    vi.spyOn(bookingApi, "pending").mockResolvedValue([booking()]);
    vi.spyOn(bookingApi, "approve").mockRejectedValue(
      new ApiError(409, "VENUE_UNAVAILABLE", [], {
        conflict: { starts_at: "2026-11-20T00:00:00Z", ends_at: "2026-11-20T01:50:00Z" },
        buffers: true,
        message: "Too close to a booking.",
      }),
    );
    const user = userEvent.setup();
    render(<PendingBookings />);

    const row = await screen.findByRole("listitem", { name: "Venue Booking Demo at Hall A" });
    await user.click(within(row).getByRole("button", { name: "Approve" }));

    expect(await within(row).findByRole("alert")).toHaveTextContent(
      "Can't approve: too close to a booking or closure on Fri, Nov 20, 8:00 AM – 9:50 AM to fit the venue's setup and turnaround. Reject the request instead.",
    );
    expect(within(row).getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Approve" })).toBeEnabled();
  });

  it.each([
    [new ApiError(409, "BOOKING_EXPIRED"), "Can't approve: this request's start time has passed. Reject it instead."],
    [
      new ApiError(409, "VENUE_CAPACITY_EXCEEDED", [], { capacity: 25 }),
      "Can't approve: expected attendance is more than the venue's capacity of 25 now. Reject the request instead.",
    ],
  ])("explains a %s refusal on the row (PR #73 review)", async (refusal, message) => {
    vi.spyOn(bookingApi, "pending").mockResolvedValue([booking()]);
    vi.spyOn(bookingApi, "approve").mockRejectedValue(refusal);
    const user = userEvent.setup();
    render(<PendingBookings />);

    const row = await screen.findByRole("listitem", { name: "Venue Booking Demo at Hall A" });
    await user.click(within(row).getByRole("button", { name: "Approve" }));

    expect(await within(row).findByRole("alert")).toHaveTextContent(message);
  });

  it("rejects with an optional reason and alternative, sending only what was written (TC-US4-04, 05)", async () => {
    vi.spyOn(bookingApi, "pending").mockResolvedValue([booking()]);
    const reject = vi.spyOn(bookingApi, "reject").mockResolvedValue(booking({ status: "rejected" }));
    const user = userEvent.setup();
    render(<PendingBookings />);

    const row = await screen.findByRole("listitem", { name: "Venue Booking Demo at Hall A" });
    await user.click(within(row).getByRole("button", { name: "Reject" }));
    const dialog = screen.getByRole("dialog", { name: "Reject this venue request?" });
    expect(reject).not.toHaveBeenCalled();
    await user.type(within(dialog).getByLabelText("Reason (optional)"), "  Being repainted  ");
    await user.click(within(dialog).getByRole("button", { name: "Reject request" }));

    expect(reject).toHaveBeenCalledWith("booking-1", { reason: "Being repainted" });
    expect(await screen.findByRole("status")).toHaveTextContent("Rejected the request for Hall A for Venue Booking Demo.");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("rejects with no notes at all (TC-US4-04)", async () => {
    vi.spyOn(bookingApi, "pending").mockResolvedValue([booking()]);
    const reject = vi.spyOn(bookingApi, "reject").mockResolvedValue(booking({ status: "rejected" }));
    const user = userEvent.setup();
    render(<PendingBookings />);

    await user.click(await screen.findByRole("button", { name: "Reject" }));
    await user.click(screen.getByRole("button", { name: "Reject request" }));

    expect(reject).toHaveBeenCalledWith("booking-1", {});
  });

  it("explains in the dialog when the request was decided meanwhile, and reloads the list", async () => {
    const pending = vi.spyOn(bookingApi, "pending").mockResolvedValueOnce([booking()]).mockResolvedValueOnce([]);
    vi.spyOn(bookingApi, "reject").mockRejectedValue(new ApiError(409, "BOOKING_NOT_PENDING", [], { status: "withdrawn" }));
    const user = userEvent.setup();
    render(<PendingBookings />);

    await user.click(await screen.findByRole("button", { name: "Reject" }));
    await user.click(screen.getByRole("button", { name: "Reject request" }));

    expect(await within(screen.getByRole("dialog")).findByRole("alert")).toHaveTextContent(
      "This request was already decided or withdrawn (it's withdrawn now). Reload the list.",
    );
    expect(pending).toHaveBeenCalledTimes(2);
  });
});
