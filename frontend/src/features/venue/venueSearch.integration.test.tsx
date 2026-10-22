import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { callsTo, seedBooking, seedVenue, server, startMockBackend } from "../../test/server";

// US2 (SCRUM-7): the real App, VenuesPage and VenueSearch against the fake backend.
startMockBackend();

beforeEach(() => setDevRole("coordinator"));

type User = ReturnType<typeof userEvent.setup>;

async function openVenues(user: User) {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Venues" }));
  return screen.findByRole("heading", { name: "Find an available venue" });
}

async function fillCore(user: User, { date = "2026-10-10", start = "10:00", end = "12:00", attendees = "30" } = {}) {
  await user.type(screen.getByLabelText("Date"), date);
  await user.type(screen.getByLabelText("Start time"), start);
  await user.type(screen.getByLabelText("End time"), end);
  await user.type(screen.getByLabelText("Expected attendance"), attendees);
}

function results() {
  return screen.getByRole("list", { name: "Available venues" });
}

function resultNames() {
  return within(results())
    .getAllByRole("listitem")
    .map((item) => item.getAttribute("aria-label"));
}

describe("venue search (US2)", () => {
  it("lists available venues with capacity, facilities and accessibility, smallest first (AC 1, 3, 4)", async () => {
    seedVenue({ name: "Mochtar Riady Auditorium", capacity: 450, facilities: ["stage", "sound_system"], accessibility_features: ["hearing_loop"] });
    seedVenue({ name: "SCIS Seminar Room 2-1", capacity: 40 });
    seedVenue({ name: "SMU Connexion Studio 3-2", capacity: 20 });
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByText("2 venues are available, smallest first.")).toBeInTheDocument();
    expect(resultNames()).toEqual(["SCIS Seminar Room 2-1", "Mochtar Riady Auditorium"]);
    const auditorium = within(results()).getByRole("listitem", { name: "Mochtar Riady Auditorium" });
    expect(auditorium).toHaveTextContent("450");
    expect(auditorium).toHaveTextContent("Stage, Sound system");
    expect(auditorium).toHaveTextContent("Hearing loop");

    const [call] = callsTo("GET", "/api/v1/venues/available");
    expect(call.headers.get("X-User-Id")).toBe("coordinator-id");
  });

  it("narrows by location, facilities and accessibility (AC 2)", async () => {
    seedVenue({ name: "Library room", location: "Li Ka Shing Library, Level 3", facilities: ["projector"], accessibility_features: ["lift"] });
    seedVenue({ name: "Library, no lift", location: "Li Ka Shing Library, Level 1", facilities: ["projector"], accessibility_features: [] });
    seedVenue({ name: "SCIS room", location: "SCIS Building", facilities: ["projector"], accessibility_features: ["lift"] });
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user);
    await user.type(screen.getByLabelText("Location"), "library");
    const search = screen.getByRole("region", { name: "Find an available venue" });
    await user.click(within(search).getByRole("checkbox", { name: "Projector" }));
    await user.click(within(search).getByRole("checkbox", { name: "Lift" }));
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByRole("list", { name: "Available venues" })).toBeInTheDocument();
    expect(resultNames()).toEqual(["Library room"]);
    const [call] = callsTo("GET", "/api/v1/venues/available");
    expect(call.url.searchParams.get("location")).toBe("library");
    expect(call.url.searchParams.getAll("facilities")).toEqual(["projector"]);
    expect(call.url.searchParams.getAll("accessibility")).toEqual(["lift"]);
  });

  it("leaves out venues that are held, booked or blocked, and those closed at that time (AC 5, 6)", async () => {
    const held = seedVenue({ name: "Held room" });
    const booked = seedVenue({ name: "Booked room" });
    const blocked = seedVenue({ name: "Blocked room" });
    seedVenue({ name: "Closes at 11", opens_at: "08:00:00", closes_at: "11:00:00" });
    seedVenue({ name: "Free room" });
    seedBooking(held, { status: "held" });
    seedBooking(booked, { status: "approved", starts: "11:00", ends: "13:00" });
    seedBooking(blocked, { status: "blocked", starts: "08:00", ends: "18:00" });
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByText("1 venue is available, smallest first.")).toBeInTheDocument();
    expect(resultNames()).toEqual(["Free room"]);
  });

  it("says no matching venues and lists the criteria applied (AC 7)", async () => {
    seedVenue({ capacity: 40 });
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user, { attendees: "500" });
    await user.type(screen.getByLabelText("Location"), "Library");
    await user.click(
      within(screen.getByRole("region", { name: "Find an available venue" })).getByRole("checkbox", { name: "Wi-Fi" }),
    );
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByText("No matching venues.")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Criteria applied" })).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Date: 2026-10-10",
      "Time: 10:00–12:00",
      "Expected attendance: 500",
      "Location: Library",
      "Facilities: Wi-Fi",
    ]);
    expect(screen.queryByRole("list", { name: "Available venues" })).not.toBeInTheDocument();
  });

  it("flags every missing criterion from the API's 422", async () => {
    const user = userEvent.setup();
    await openVenues(user);

    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Complete the fields marked below.");
    for (const label of ["Date", "Start time", "End time", "Expected attendance"]) {
      expect(screen.getByLabelText(label)).toHaveAttribute("aria-invalid", "true");
    }
    // Fixing a field clears its flag only.
    await user.type(screen.getByLabelText("Date"), "2026-10-10");
    expect(screen.getByLabelText("Date")).not.toHaveAttribute("aria-invalid");
    expect(screen.getByLabelText("End time")).toHaveAttribute("aria-invalid", "true");
  });

  it("shows the API's message on an invalid time range", async () => {
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user, { start: "14:00", end: "12:00" });
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    const endTime = await screen.findByLabelText("End time");
    expect(endTime).toHaveAttribute("aria-invalid", "true");
    expect(endTime).toHaveAccessibleDescription("The end time must be after the start time (events can't cross midnight).");
  });

  it("clears the form and results", async () => {
    seedVenue({ name: "Free room" });
    const user = userEvent.setup();
    await openVenues(user);
    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));
    await screen.findByRole("list", { name: "Available venues" });

    await user.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.queryByRole("list", { name: "Available venues" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Expected attendance")).toHaveValue(null);
  });

  it("is offered to venue staff too, but not to organisers (D20)", async () => {
    seedVenue({ name: "Catalogue room" });
    setDevRole("venue_staff");
    const user = userEvent.setup();
    await openVenues(user);
    expect(screen.getByRole("heading", { name: "All venues" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Acting as"), "organiser");
    // The catalogue stays; the search form goes.
    expect(await screen.findByRole("listitem", { name: "Catalogue room" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Find an available venue" })).not.toBeInTheDocument();
  });

  it("reports an unreachable backend instead of an empty result", async () => {
    const user = userEvent.setup();
    await openVenues(user);
    server.use(http.get("http://api.test/api/v1/venues/available", () => HttpResponse.error()));

    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Check the backend connection");
    expect(screen.queryByText("No matching venues.")).not.toBeInTheDocument();
  });
});
