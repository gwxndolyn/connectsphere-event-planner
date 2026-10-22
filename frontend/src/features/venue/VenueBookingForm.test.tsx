import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import type { EventRequest } from "../eventRequest/types";
import { venueApi } from "./api";
import { bookingApi } from "./bookingApi";
import type { VenueBookingCreated } from "./bookingTypes";
import type { Venue } from "./types";
import { VenueBookingForm } from "./VenueBookingForm";

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

function venue(overrides: Partial<Venue> = {}): Venue {
  return {
    id: "venue-1",
    name: "Hall A",
    location: "Building 1",
    capacity: 40,
    facilities: ["projector"],
    accessibility_features: [],
    room_layouts: ["theatre"],
    opens_at: "08:00:00",
    closes_at: "22:00:00",
    setup_minutes: 0,
    turnaround_minutes: 0,
    is_active: true,
    ...overrides,
  };
}

const CREATED = { id: "booking-1", status: "requested", warnings: [] } as unknown as VenueBookingCreated;

let create: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.spyOn(venueApi, "list").mockResolvedValue([venue(), venue({ id: "venue-2", name: "Room B", capacity: 12, room_layouts: ["classroom"] })]);
  create = vi.spyOn(bookingApi, "create").mockResolvedValue(CREATED);
});

async function renderForm() {
  const onBooked = vi.fn();
  render(<VenueBookingForm event={EVENT} onBooked={onBooked} onCancel={vi.fn()} />);
  await screen.findByRole("option", { name: "Hall A (capacity 40)" });
  return { user: userEvent.setup(), onBooked };
}

describe("VenueBookingForm (US22, SCRUM-113)", () => {
  it("starts from the event's preferred date, times and attendance (AC 2)", async () => {
    await renderForm();

    expect(screen.getByLabelText("Date")).toHaveValue("2026-11-20");
    expect(screen.getByLabelText("Start time")).toHaveValue("14:00");
    expect(screen.getByLabelText("End time")).toHaveValue("16:00");
    expect(screen.getByLabelText("Expected attendance")).toHaveValue(40);
  });

  it("sends every field to the API and hands back what it booked", async () => {
    const { user, onBooked } = await renderForm();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.click(screen.getByRole("checkbox", { name: "Projector" }));
    await user.type(screen.getByLabelText("Special requirements"), "Lectern, please");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(create).toHaveBeenCalledWith({
      event_id: "event-1",
      venue_id: "venue-1",
      starts_at: "2026-11-20T14:00:00+08:00",
      ends_at: "2026-11-20T16:00:00+08:00",
      expected_attendees: 40,
      room_layout: "theatre",
      required_facilities: ["projector"],
      required_accessibility_features: [],
      special_requirements: "Lectern, please",
    });
    expect(onBooked).toHaveBeenCalledWith(CREATED);
  });

  it("warns before sending when the venue lacks a requirement, and still sends (TC-US22-20, AC 3)", async () => {
    const { user, onBooked } = await renderForm();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    await user.selectOptions(screen.getByLabelText("Layout"), "classroom");
    await user.click(screen.getByRole("checkbox", { name: "Stage" }));
    await user.click(screen.getByRole("checkbox", { name: "Wheelchair" }));

    expect(screen.getByText("This venue doesn't have: Stage, Wheelchair, Classroom layout. You can still send the request.")).toBeInTheDocument();

    // A venue that has the layout drops that item from the warning.
    await user.selectOptions(screen.getByLabelText("Venue"), "venue-2");
    expect(screen.getByText("This venue doesn't have: Stage, Wheelchair. You can still send the request.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(onBooked).toHaveBeenCalledOnce();
  });

  it("shows VENUE_CAPACITY_EXCEEDED on the attendance field (TC-US22-20)", async () => {
    create.mockRejectedValue(
      new ApiError(422, "VENUE_CAPACITY_EXCEEDED", ["expected_attendees"], {
        capacity: 12,
        message: "Expected attendance is more than this venue's capacity of 12.",
      }),
    );
    const { user, onBooked } = await renderForm();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-2");
    await user.selectOptions(screen.getByLabelText("Layout"), "classroom");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    const attendance = screen.getByLabelText("Expected attendance");
    expect(attendance).toHaveAttribute("aria-invalid", "true");
    expect(attendance).toHaveAccessibleDescription("Expected attendance is more than this venue's capacity of 12.");
    expect(screen.getByRole("alert")).toHaveTextContent("capacity of 12");
    expect(onBooked).not.toHaveBeenCalled();

    // Editing the field clears its error.
    await user.clear(attendance);
    expect(attendance).not.toHaveAttribute("aria-invalid");
  });

  it("shows VENUE_UNAVAILABLE with the clashing window (AC 3)", async () => {
    create.mockRejectedValue(
      new ApiError(409, "VENUE_UNAVAILABLE", [], {
        conflict: { starts_at: "2026-11-20T05:00:00+00:00", ends_at: "2026-11-20T07:00:00+00:00" },
      }),
    );
    const { user } = await renderForm();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "This venue is already booked or unavailable on Fri, Nov 20, 1:00 PM – 3:00 PM.",
    );
    expect(screen.getByLabelText("Start time")).toHaveAccessibleDescription("Clashes with Fri, Nov 20, 1:00 PM – 3:00 PM.");
  });

  it("marks the fields INVALID_BOOKING and MISSING_REQUIRED_FIELD name", async () => {
    create.mockRejectedValueOnce(new ApiError(422, "MISSING_REQUIRED_FIELD", ["venue_id", "room_layout"]));
    const { user } = await renderForm();

    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(screen.getByLabelText("Venue")).toHaveAccessibleDescription("Required.");
    expect(screen.getByLabelText("Layout")).toHaveAccessibleDescription("Required.");

    create.mockRejectedValueOnce(
      new ApiError(422, "INVALID_BOOKING", ["starts_at", "ends_at"], {
        errors: { starts_at: "Start time can't be in the past.", ends_at: "End time must be after the start time." },
      }),
    );
    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(screen.getByLabelText("Start time")).toHaveAccessibleDescription("Start time can't be in the past.");
    expect(screen.getByLabelText("End time")).toHaveAccessibleDescription("End time must be after the start time.");
    expect(screen.getByLabelText("Venue")).not.toHaveAttribute("aria-invalid");
  });
});
