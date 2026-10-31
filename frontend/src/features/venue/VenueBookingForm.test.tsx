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
    expect(screen.getByLabelText("Allocated attendees")).toHaveValue(40);
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

    const attendance = screen.getByLabelText("Allocated attendees");
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

describe("VenueBookingForm buffers (US13, SCRUM-116)", () => {
  it("previews the window the chosen venue's setup and turnaround occupy, as the times change (TC-US13-16, AC 2)", async () => {
    vi.spyOn(venueApi, "list").mockResolvedValue([venue({ setup_minutes: 30, turnaround_minutes: 45 })]);
    const { user } = await renderForm();
    expect(screen.queryByText(/The venue is occupied/)).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    // The event's preferred 14:00–16:00.
    expect(screen.getByText("The venue is occupied 1:30 PM – 4:45 PM (30 min setup, 45 min turnaround). Open 8:00 AM – 10:00 PM.")).toBeInTheDocument();

    await user.clear(screen.getByLabelText("End time"));
    await user.type(screen.getByLabelText("End time"), "17:00");
    expect(screen.getByText(/^The venue is occupied 1:30 PM – 5:45 PM/)).toBeInTheDocument();

    await user.clear(screen.getByLabelText("Start time"));
    expect(screen.getByText("This venue needs 30 min setup, 45 min turnaround. Open 8:00 AM – 10:00 PM.")).toBeInTheDocument();
  });

  it("shows VENUE_OUTSIDE_HOURS on the time field that breaches, until it's changed (TC-US13-17, AC 5)", async () => {
    create.mockRejectedValue(
      new ApiError(422, "VENUE_OUTSIDE_HOURS", ["ends_at"], {
        opens_at: "08:00:00",
        closes_at: "16:00:00",
        occupied: { starts_at: "2026-11-20T06:00:00+00:00", ends_at: "2026-11-20T08:15:00+00:00" },
      }),
    );
    const { user, onBooked } = await renderForm();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "With setup and turnaround the venue would be occupied 2:00 PM – 4:15 PM, outside its opening hours of 8:00 AM – 4:00 PM. Choose times that fit.",
    );
    const end = screen.getByLabelText("End time");
    expect(end).toHaveAttribute("aria-invalid", "true");
    expect(end).toHaveAccessibleDescription("With turnaround, ends after the venue closes at 4:00 PM.");
    expect(screen.getByLabelText("Start time")).not.toHaveAttribute("aria-invalid");
    expect(onBooked).not.toHaveBeenCalled();

    await user.clear(end);
    expect(end).not.toHaveAttribute("aria-invalid");
  });

  it("clears VENUE_OUTSIDE_HOURS on the end time when the start time is edited (PR #83 review)", async () => {
    create.mockRejectedValue(
      new ApiError(422, "VENUE_OUTSIDE_HOURS", ["ends_at"], {
        opens_at: "08:00:00",
        closes_at: "16:00:00",
        occupied: { starts_at: "2026-11-20T06:00:00+00:00", ends_at: "2026-11-20T08:15:00+00:00" },
      }),
    );
    const { user } = await renderForm();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    const end = screen.getByLabelText("End time");
    expect(end).toHaveAttribute("aria-invalid", "true");

    await user.clear(screen.getByLabelText("Start time"));
    expect(end).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByText("With turnaround, ends after the venue closes at 4:00 PM.")).not.toBeInTheDocument();
  });

  it("shows VENUE_UNAVAILABLE's overlap period on the start time (TC-US13-17, AC 3, 4)", async () => {
    create.mockRejectedValue(
      new ApiError(409, "VENUE_UNAVAILABLE", [], {
        conflict: {
          kind: "booking",
          starts_at: "2026-11-20T04:00:00+00:00",
          ends_at: "2026-11-20T06:00:00+00:00",
          occupied: { starts_at: "2026-11-20T03:30:00+00:00", ends_at: "2026-11-20T06:15:00+00:00" },
          overlap: { starts_at: "2026-11-20T06:00:00+00:00", ends_at: "2026-11-20T06:15:00+00:00" },
        },
      }),
    );
    const { user } = await renderForm();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-1");
    await user.selectOptions(screen.getByLabelText("Layout"), "theatre");
    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "This venue is already booked on Fri, Nov 20, 12:00 PM – 2:00 PM. With setup and turnaround, that overlaps your request 2:00 PM – 2:15 PM.",
    );
    expect(screen.getByLabelText("Start time")).toHaveAccessibleDescription(
      "With setup and turnaround, overlaps another booking 2:00 PM – 2:15 PM.",
    );
  });
});

describe("VenueBookingForm for one of several venues (US24, TC-US24-20)", () => {
  it("asks how many attendees this venue takes and says what it holds (AC 3, D67)", async () => {
    const { user } = await renderForm();

    await user.selectOptions(screen.getByLabelText("Venue"), "venue-2");

    expect(screen.getByLabelText("Allocated attendees")).toHaveValue(40);
    expect(screen.getByText("Room B holds 12.")).toBeInTheDocument();
  });

  it("shows the event's preferred schedule while it has no dates of its own (D65)", async () => {
    render(
      <VenueBookingForm
        event={{ ...EVENT, preferred_dates: ["2026-11-20", "2026-11-21"] }}
        onBooked={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(await screen.findByText("Event schedule: Fri, Nov 20 or Sat, Nov 21, 2:00 PM – 4:00 PM")).toBeInTheDocument();
  });

  it("shows the event's own start and end once it has them, not its preferences (D65)", async () => {
    render(
      <VenueBookingForm
        event={{ ...EVENT, start_at: "2026-11-20T02:00:00Z", end_at: "2026-11-20T09:00:00Z" }}
        onBooked={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(await screen.findByText("Event schedule: Fri, Nov 20, 10:00 AM – 5:00 PM")).toBeInTheDocument();
    expect(screen.queryByText(/2:00 PM – 4:00 PM/)).not.toBeInTheDocument();
  });

  it("shows nothing for an event with no schedule at all", async () => {
    render(
      <VenueBookingForm
        event={{ ...EVENT, preferred_dates: null, preferred_start_time: null, preferred_end_time: null }}
        onBooked={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    await screen.findByRole("option", { name: "Hall A (capacity 40)" });

    expect(screen.queryByText(/^Event schedule/)).not.toBeInTheDocument();
  });

  it("shows INVALID_BOOKING's schedule and purpose errors on their fields", async () => {
    create.mockRejectedValue(
      new ApiError(422, "INVALID_BOOKING", ["starts_at", "purpose"], {
        code: "INVALID_BOOKING",
        fields: ["starts_at", "purpose"],
        errors: {
          starts_at: "Starts before the event's schedule (14:00 to 16:00).",
          purpose: "Keep the purpose to 100 characters.",
        },
      }),
    );
    const { user } = await renderForm();

    await user.click(screen.getByRole("button", { name: "Send request" }));

    expect(await screen.findByLabelText("Start time")).toHaveAccessibleDescription(
      "Starts before the event's schedule (14:00 to 16:00).",
    );
    expect(screen.getByLabelText("Purpose")).toHaveAccessibleDescription("Keep the purpose to 100 characters.");
  });
});
