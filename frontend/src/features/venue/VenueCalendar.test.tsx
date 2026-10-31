import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { venueApi } from "./api";
import { bookingApi } from "./bookingApi";
import type { CalendarItem, Venue, VenueCalendar as Calendar } from "./types";
import { VenueCalendar } from "./VenueCalendar";

// US21 (SCRUM-88, PR 2 SCRUM-123): the calendar screen, with venueApi stubbed. Wed 14 Oct 2026, so
// the week is Mon 12 to Sun 18 Oct. Hall A opens 08:00–20:00 with 30 min setup, 15 min turnaround.
const TODAY = "2026-10-14";

const HALL: Venue = {
  id: "venue-1",
  name: "Hall A",
  location: "Building 1",
  capacity: 40,
  facilities: [],
  accessibility_features: [],
  room_layouts: [],
  opens_at: "08:00:00",
  closes_at: "20:00:00",
  setup_minutes: 30,
  turnaround_minutes: 15,
  is_active: true,
};

function booking(overrides: Partial<NonNullable<CalendarItem["booking"]>> = {}): CalendarItem {
  return {
    kind: "booking",
    label: "Booking",
    // Mon 12 Oct, 10:00–12:00 Singapore, occupied 09:30–12:15.
    starts_at: "2026-10-12T02:00:00Z",
    ends_at: "2026-10-12T04:00:00Z",
    occupied: { starts_at: "2026-10-12T01:30:00Z", ends_at: "2026-10-12T04:15:00Z" },
    booking: {
      id: "booking-1",
      reference: "VB-2026-000001",
      status: "approved",
      event: { name: "Design Review", request_reference: null, status: "approved" },
      // US24 (D73): how far Venue staff are with getting it ready.
      preparation_status: "not_started",
      ...overrides,
    },
    note: null,
  };
}

// Wed 14 Oct, 13:00–15:00 Singapore.
const BLOCK: CalendarItem = {
  kind: "block",
  label: "Unavailable",
  starts_at: "2026-10-14T05:00:00Z",
  ends_at: "2026-10-14T07:00:00Z",
  occupied: { starts_at: "2026-10-14T05:00:00Z", ends_at: "2026-10-14T07:00:00Z" },
  booking: null,
  note: "Aircon repair",
};

function calendarOf(items: CalendarItem[]): Calendar {
  const { id, name, is_active, opens_at, closes_at, setup_minutes, turnaround_minutes } = HALL;
  return {
    venue: { id, name, is_active, opens_at, closes_at, setup_minutes, turnaround_minutes },
    from: "2026-10-12",
    to: "2026-10-18",
    items,
  };
}

let calendar: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.spyOn(venueApi, "list").mockResolvedValue([HALL]);
  calendar = vi.spyOn(venueApi, "calendar").mockResolvedValue(calendarOf([]));
});

type User = ReturnType<typeof userEvent.setup>;

async function openHall(user: User, items?: CalendarItem[], staff = false) {
  if (items) calendar.mockResolvedValue(calendarOf(items));
  render(<VenueCalendar staff={staff} today={TODAY} />);
  await user.selectOptions(await screen.findByLabelText("Venue"), "Hall A");
}

function day(name: string) {
  return within(screen.getByRole("group", { name }));
}

describe("VenueCalendar week view (US21)", () => {
  it("TC-US21-17: a booking spans its occupied window, with setup and turnaround named (AC 2)", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking()]);

    const item = await screen.findByRole("button", {
      name: "Booking: Design Review, 10:00 AM – 12:00 PM, occupied 9:30 AM – 12:15 PM",
    });
    expect(day("Mon, Oct 12").getByRole("button", { name: /^Booking: Design Review/ })).toBe(item);
    expect(within(item).getByText("Setup 30 min")).toBeInTheDocument();
    expect(within(item).getByText("Turnaround 15 min")).toBeInTheDocument();
    // 07:00 to 21:00 is drawn (an hour either side of opening); 09:30–12:15 sits 150 minutes in, 165 long.
    expect(parseFloat(item.style.top)).toBeCloseTo((150 / 840) * 100);
    expect(parseFloat(item.style.height)).toBeCloseTo((165 / 840) * 100);
    expect(calendar).toHaveBeenCalledWith("venue-1", "2026-10-12", "2026-10-18");
  });

  it("TC-US21-18: a Requested booking reads as pending, a block as Unavailable with its note (AC 1, D57)", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking({ status: "requested" }), BLOCK]);

    const pending = await screen.findByRole("button", { name: /^Booking \(requested\): Design Review/ });
    expect(pending).toHaveClass("venue-calendar__item--pending");
    expect(within(pending).getByText("Booking (requested)")).toBeInTheDocument();
    const closure = day("Wed, Oct 14").getByRole("button", { name: "Unavailable: Aircon repair, 1:00 PM – 3:00 PM" });
    expect(within(closure).getByText("Aircon repair")).toBeInTheDocument();
    expect(closure).not.toHaveClass("venue-calendar__item--pending");
  });

  it("TC-US21-18: a booking for a cancelled event reads \"Booking (event cancelled)\", muted, in the week and month views (D60)", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking({ event: { name: "Design Review", request_reference: null, status: "cancelled" } })]);
    const name = "Booking (event cancelled): Design Review, 10:00 AM – 12:00 PM, occupied 9:30 AM – 12:15 PM";

    const week = await screen.findByRole("button", { name });
    expect(week).toHaveClass("venue-calendar__item--cancelled");
    expect(within(week).getByText("Booking (event cancelled)")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Month" }));
    const chip = await day("Mon, Oct 12").findByRole("button", { name });
    expect(chip).toHaveClass("venue-calendar__item--cancelled");
    expect(chip).toHaveTextContent("Booking (event cancelled) 9:30 AM – 12:15 PM");
  });

  it("TC-US21-19: hours outside the venue's opening hours are shaded Closed on every day (D61)", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking()]);
    await screen.findByRole("button", { name: /^Booking: Design Review/ });

    for (const name of ["Mon, Oct 12", "Tue, Oct 13", "Wed, Oct 14", "Thu, Oct 15", "Fri, Oct 16", "Sat, Oct 17", "Sun, Oct 18"]) {
      expect(day(name).getAllByText("Closed")).toHaveLength(2);
    }
  });
});

describe("VenueCalendar item details (TC-US21-20, AC 3)", () => {
  it("shows the event's name and status, the booking's status, times and reference", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking()]);

    await user.click(await screen.findByRole("button", { name: /^Booking: Design Review/ }));

    const dialog = within(screen.getByRole("dialog", { name: "Booking" }));
    expect(dialog.getByText("Design Review")).toBeInTheDocument();
    expect(dialog.getByText("Event status").nextElementSibling).toHaveTextContent("approved");
    expect(dialog.getByText("Booking status").nextElementSibling).toHaveTextContent("Approved");
    expect(dialog.getByText("Mon, Oct 12, 10:00 AM – 12:00 PM")).toBeInTheDocument();
    expect(dialog.getByText("9:30 AM – 12:15 PM with setup and turnaround")).toBeInTheDocument();
    expect(dialog.getByText("Reference").nextElementSibling).toHaveTextContent("VB-2026-000001");
    expect(dialog.queryByRole("link")).not.toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("leaves the reference out when the API doesn't give one (D58)", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking({ reference: null, status: "requested" })]);

    await user.click(await screen.findByRole("button", { name: /^Booking \(requested\)/ }));

    const dialog = within(screen.getByRole("dialog", { name: "Booking (requested)" }));
    expect(dialog.getByText("Design Review")).toBeInTheDocument();
    expect(dialog.getByText("Booking status").nextElementSibling).toHaveTextContent("Requested");
    expect(dialog.queryByText("Reference")).not.toBeInTheDocument();
    expect(dialog.queryByText(/VB-/)).not.toBeInTheDocument();
  });

  it("names an unnamed event by its request reference, and shows a cancelled event as cancelled (D60)", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking({ event: { name: null, request_reference: "ER-2026-000007", status: "cancelled" } })]);

    await user.click(await screen.findByRole("button", { name: /^Booking \(event cancelled\): ER-2026-000007/ }));

    const dialog = within(screen.getByRole("dialog", { name: "Booking (event cancelled)" }));
    expect(dialog.getByText("Event status").nextElementSibling).toHaveTextContent("cancelled");
  });

  it("shows a block's times and note", async () => {
    const user = userEvent.setup();
    await openHall(user, [BLOCK]);

    await user.click(await screen.findByRole("button", { name: /^Unavailable: Aircon repair/ }));

    const dialog = within(screen.getByRole("dialog", { name: "Unavailable" }));
    expect(dialog.getByText("Wed, Oct 14, 1:00 PM – 3:00 PM")).toBeInTheDocument();
    expect(dialog.getByText("Note").nextElementSibling).toHaveTextContent("Aircon repair");
    await user.click(dialog.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("VenueCalendar states (TC-US21-22)", () => {
  it("asks for a venue first, and fetches nothing until one is chosen", async () => {
    render(<VenueCalendar staff={false} today={TODAY} />);

    expect(await screen.findByText("Choose a venue to see its calendar.")).toBeInTheDocument();
    expect(calendar).not.toHaveBeenCalled();
  });

  it("says when it's loading, then when nothing is booked or blocked", async () => {
    const user = userEvent.setup();
    let answer: (value: Calendar) => void = () => {};
    calendar.mockReturnValue(new Promise<Calendar>((resolve) => (answer = resolve)));
    render(<VenueCalendar staff={false} today={TODAY} />);
    await user.selectOptions(await screen.findByLabelText("Venue"), "Hall A");

    expect(screen.getByText("Loading calendar…")).toBeInTheDocument();
    answer(calendarOf([]));
    expect(await screen.findByText("Nothing booked or blocked at Hall A this week.")).toBeInTheDocument();
  });

  it.each([
    [new ApiError(403, "FORBIDDEN"), "Only coordinators, Leads and Venue staff can see venue calendars. Switch Acting as."],
    [new ApiError(404, "NOT_FOUND"), "This venue is no longer available. Choose another venue."],
    [
      new ApiError(422, "INVALID_DATE_RANGE", ["to"], { code: "INVALID_DATE_RANGE", message: "At most 42 days." }),
      "At most 42 days.",
    ],
    [new TypeError("Failed to fetch"), "The request could not be completed. Check the backend connection and try again."],
  ])("shows %s in an alert", async (refusal, message) => {
    const user = userEvent.setup();
    calendar.mockRejectedValue(refusal);
    await openHall(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });
});

describe("VenueCalendar preparation status (US24, TC-US24-29, D73, D78)", () => {
  it("lets Venue staff set an approved booking's preparation status in its details", async () => {
    const user = userEvent.setup();
    const setPreparation = vi.spyOn(bookingApi, "setPreparation").mockResolvedValue({
      id: "booking-1",
      preparation_status: "in_progress",
    } as Awaited<ReturnType<typeof bookingApi.setPreparation>>);
    await openHall(user, [booking()], true);

    await user.click(await screen.findByRole("button", { name: /^Booking: Design Review/ }));
    const dialog = within(screen.getByRole("dialog", { name: "Booking" }));
    const control = dialog.getByRole("combobox", { name: "Preparation" });
    expect(control).toHaveValue("not_started");
    await user.selectOptions(control, "in_progress");
    await user.click(dialog.getByRole("button", { name: "Save preparation" }));

    expect(setPreparation).toHaveBeenCalledWith("booking-1", "in_progress");
    expect(await dialog.findByRole("status")).toHaveTextContent("Preparation saved: In progress.");
    // The calendar keeps it: reopening shows the new status.
    await user.click(dialog.getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: /^Booking: Design Review/ }));
    expect(screen.getByRole("combobox", { name: "Preparation" })).toHaveValue("in_progress");
  });

  it("shows the API's refusal and reloads the calendar", async () => {
    const user = userEvent.setup();
    vi.spyOn(bookingApi, "setPreparation").mockRejectedValue(
      new ApiError(409, "BOOKING_NOT_APPROVED", [], { code: "BOOKING_NOT_APPROVED", status: "withdrawn" }),
    );
    await openHall(user, [booking()], true);
    await user.click(await screen.findByRole("button", { name: /^Booking: Design Review/ }));
    const calls = calendar.mock.calls.length;

    await user.click(screen.getByRole("button", { name: "Save preparation" }));

    expect(await within(screen.getByRole("dialog")).findByRole("alert")).toHaveTextContent(
      "Only an approved booking is prepared; this one is withdrawn now.",
    );
    expect(calendar.mock.calls.length).toBeGreaterThan(calls);
  });

  it("shows coordinators and Leads the status read-only", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking({ preparation_status: "ready" })]);

    await user.click(await screen.findByRole("button", { name: /^Booking: Design Review/ }));

    const dialog = within(screen.getByRole("dialog", { name: "Booking" }));
    expect(dialog.getByText("Preparation").nextElementSibling).toHaveTextContent("Ready");
    expect(dialog.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("has nothing to prepare on a booking that isn't approved", async () => {
    const user = userEvent.setup();
    await openHall(user, [booking({ status: "requested" })], true);

    await user.click(await screen.findByRole("button", { name: /^Booking \(requested\)/ }));

    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.queryByText("Preparation")).not.toBeInTheDocument();
    expect(dialog.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
