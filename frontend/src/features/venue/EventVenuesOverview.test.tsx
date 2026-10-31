import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { EventRequest } from "../eventRequest/types";
import { bookingApi } from "./bookingApi";
import type { EventVenueBooking, EventVenues } from "./bookingTypes";
import { EventVenuesOverview } from "./EventVenuesOverview";

// US24 AC 4 (SCRUM-129, D71): the Organiser's read-only view of an approved event's venues.
const EVENT = { id: "event-1", name: "Data Conference", status: "approved", request_reference: "ER-2026-000001" } as EventRequest;

function booking(overrides: Partial<EventVenueBooking> = {}): EventVenueBooking {
  return {
    id: "booking-1",
    reference: "VB-2026-000001",
    event: { id: "event-1", name: "Data Conference", request_reference: "ER-2026-000001", status: "approved" },
    venue: { id: "venue-1", name: "Main Hall", location: "Building 1", capacity: 300 },
    requested_by_user_id: "coordinator-id",
    starts_at: "2026-11-20T01:00:00Z",
    ends_at: "2026-11-20T09:00:00Z",
    occupied_starts_at: "2026-11-20T00:00:00Z",
    occupied_ends_at: "2026-11-20T09:45:00Z",
    expected_attendees: 300,
    room_layout: "theatre",
    required_facilities: [],
    required_accessibility_features: [],
    special_requirements: null,
    status: "approved",
    created_at: "2026-10-01T02:00:00Z",
    updated_at: "2026-10-01T02:00:00Z",
    withdrawn_at: null,
    decided_at: "2026-10-02T02:00:00Z",
    decided_by_user_id: "venue-staff-id",
    rejection_reason: null,
    alternative_suggestion: null,
    purpose: "Main hall",
    is_primary: true,
    preparation_status: "in_progress",
    unavailability: null,
    next_action: "none",
    ...overrides,
  };
}

const BREAKOUT_A = booking({
  id: "booking-2",
  venue: { id: "venue-2", name: "Seminar Room", location: "Building 2", capacity: 40 },
  starts_at: "2026-11-20T05:00:00Z",
  ends_at: "2026-11-20T07:00:00Z",
  status: "requested",
  decided_at: null,
  decided_by_user_id: null,
  purpose: "Breakout A",
  is_primary: false,
  preparation_status: "not_started",
  expected_attendees: 40,
  next_action: "venue_staff_to_decide",
});

const BREAKOUT_B = booking({
  id: "booking-3",
  venue: { id: "venue-3", name: "Library Room", location: "Library", capacity: 60 },
  starts_at: "2026-11-20T05:00:00Z",
  ends_at: "2026-11-20T07:00:00Z",
  status: "rejected",
  purpose: "Breakout B",
  is_primary: false,
  preparation_status: "not_started",
  expected_attendees: 60,
  rejection_reason: "Closed that afternoon",
  alternative_suggestion: "Try the Seminar Room",
  unavailability: { kind: "rejected", reason: "Closed that afternoon", alternative_suggestion: "Try the Seminar Room" },
  next_action: "coordinator_to_rebook",
});

function venues(overrides: Partial<EventVenues> = {}): EventVenues {
  return {
    bookings: [booking(), BREAKOUT_A, BREAKOUT_B],
    venues_arranged: false,
    primary_booking_id: "booking-1",
    allocated_attendees: 340,
    expected_attendees: 300,
    next_action: null,
    ...overrides,
  };
}

let read: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  read = vi.spyOn(bookingApi, "eventVenues").mockResolvedValue(venues());
});

function venueRow(name: RegExp) {
  return within(screen.getByRole("list", { name: "This event's venues" })).getByRole("listitem", { name });
}

describe("EventVenuesOverview (US24, TC-US24-24)", () => {
  it("lists every venue with its purpose, window, status and the Primary badge", async () => {
    render(<EventVenuesOverview event={EVENT} />);

    const main = await screen.findByRole("listitem", { name: /^Main hall/ });
    expect(main).toHaveAccessibleName("Main hall: Main Hall, Fri, Nov 20, 9:00 AM – 5:00 PM");
    expect(within(main).getByText("Approved")).toBeInTheDocument();
    expect(within(main).getByText("Primary")).toBeInTheDocument();
    expect(read).toHaveBeenCalledWith("event-1");
  });

  it("says why a venue needs replacing and who acts next", async () => {
    render(<EventVenuesOverview event={EVENT} />);
    await screen.findByRole("listitem", { name: /^Main hall/ });

    const rejected = venueRow(/^Breakout B/);
    expect(within(rejected).getByText("Rejected")).toBeInTheDocument();
    expect(rejected).toHaveTextContent("Venue staff rejected it: Closed that afternoon. Suggested instead: Try the Seminar Room");
    expect(rejected).toHaveTextContent("Next: Coordinator to rebook");
    expect(venueRow(/^Breakout A/)).toHaveTextContent("Next: Waiting for Venue staff");
    expect(venueRow(/^Main hall/)).toHaveTextContent("Next: Nothing to do");
  });

  it.each([".", "!", "?"])("doesn't add a full stop to a reason that ends in %s", async (end) => {
    const reason = `The library is closed to events that afternoon${end}`;
    read.mockResolvedValue(
      venues({
        bookings: [
          { ...BREAKOUT_B, rejection_reason: reason, alternative_suggestion: null, unavailability: { kind: "rejected", reason, alternative_suggestion: null } },
        ],
      }),
    );
    render(<EventVenuesOverview event={EVENT} />);

    const rejected = await screen.findByRole("listitem", { name: /^Breakout B/ });
    expect(within(rejected).getByText(`Venue staff rejected it: ${reason}`, { exact: true })).toBeInTheDocument();
  });

  it("says when an approved venue is no longer available", async () => {
    read.mockResolvedValue(
      venues({
        bookings: [
          booking({
            unavailability: { kind: "venue_inactive", reason: null, alternative_suggestion: null },
            next_action: "coordinator_to_rebook",
          }),
        ],
      }),
    );
    render(<EventVenuesOverview event={EVENT} />);

    expect(await screen.findByRole("listitem", { name: /^Main hall/ })).toHaveTextContent(
      "This venue is no longer available.",
    );
  });

  it("TC-US24-29: shows an approved venue's preparation status, read-only", async () => {
    render(<EventVenuesOverview event={EVENT} />);

    expect(await screen.findByRole("listitem", { name: /^Main hall/ })).toHaveTextContent("Preparation: In progress");
    expect(venueRow(/^Breakout A/)).not.toHaveTextContent("Preparation");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("says whether the venues are arranged and what's missing, with no actions", async () => {
    render(<EventVenuesOverview event={EVENT} />);

    const summary = await screen.findByRole("region", { name: "Venue arrangements" });
    expect(summary).toHaveTextContent("Venues not arranged");
    expect(within(summary).getByRole("list", { name: "What's missing" })).toHaveTextContent("1 waiting for Venue staff");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("says the coordinator has to choose a primary venue when there's none", async () => {
    read.mockResolvedValue(venues({ primary_booking_id: null, next_action: "choose_primary" }));
    render(<EventVenuesOverview event={EVENT} />);

    const summary = await screen.findByRole("region", { name: "Venue arrangements" });
    expect(within(summary).getByRole("list", { name: "What's missing" })).toHaveTextContent(
      "The coordinator to choose a primary venue",
    );
  });

  it("says the venues are arranged", async () => {
    read.mockResolvedValue(venues({ bookings: [booking()], venues_arranged: true, allocated_attendees: 300 }));
    render(<EventVenuesOverview event={EVENT} />);

    expect(await screen.findByRole("region", { name: "Venue arrangements" })).toHaveTextContent("Venues arranged");
  });

  it("says so when no venue is booked yet, and shows a refusal in an alert", async () => {
    read.mockResolvedValue(venues({ bookings: [], allocated_attendees: 0 }));
    const { unmount } = render(<EventVenuesOverview event={EVENT} />);
    expect(await screen.findByText("No venue has been requested for this event yet.")).toBeInTheDocument();
    unmount();

    read.mockRejectedValue(new ApiError(404, "NOT_FOUND"));
    render(<EventVenuesOverview event={EVENT} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("This event's venues can't be shown right now.");
  });
});
