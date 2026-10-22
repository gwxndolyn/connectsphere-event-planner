import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { callsTo, nextSearchResult, seedVenue, server, startMockBackend } from "../../test/server";

// US2 (SCRUM-7): the real App, VenuesPage and VenueSearch against the fake backend. The fake
// returns whatever `nextSearchResult` queues, so these tests check what the screen sends and how it
// shows the answer. Which venues fit (AC 4 to 6) is the API's rule, tested in
// backend/tests/venue/test_venue_search.py and e2e/tests/venue-search.spec.ts, not here.
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

function searchForm() {
  return within(screen.getByRole("region", { name: "Find an available venue" }));
}

function lastSearch() {
  return callsTo("GET", "/api/v1/venues/available").at(-1)!;
}

function criteriaLines() {
  return within(screen.getByRole("list", { name: "Criteria applied" }))
    .getAllByRole("listitem")
    .map((item) => item.textContent);
}

describe("venue search (US2)", () => {
  it("sends the core criteria with the coordinator's id (AC 1)", async () => {
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));
    await screen.findByText("No matching venues.");

    const call = lastSearch();
    expect(call.headers.get("X-User-Id")).toBe("coordinator-id");
    expect(Object.fromEntries(call.url.searchParams)).toEqual({
      date: "2026-10-10",
      start_time: "10:00",
      end_time: "12:00",
      attendees: "30",
    });
  });

  it("sends location, facilities and accessibility as filters (AC 2)", async () => {
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user);
    await user.type(screen.getByLabelText("Location"), " library ");
    await user.click(searchForm().getByRole("checkbox", { name: "Projector" }));
    await user.click(searchForm().getByRole("checkbox", { name: "Stage" }));
    await user.click(searchForm().getByRole("checkbox", { name: "Lift" }));
    await user.click(screen.getByRole("button", { name: "Search venues" }));
    await screen.findByText("No matching venues.");

    const { url } = lastSearch();
    expect(url.searchParams.get("location")).toBe("library");
    expect(url.searchParams.getAll("facilities")).toEqual(["projector", "stage"]);
    expect(url.searchParams.getAll("accessibility")).toEqual(["lift"]);
  });

  it("shows each result's capacity, facilities and accessibility, in the API's order (AC 3)", async () => {
    nextSearchResult([
      seedVenue({ name: "SCIS Seminar Room 2-1", capacity: 40, facilities: [], accessibility_features: [] }),
      seedVenue({
        name: "Mochtar Riady Auditorium",
        capacity: 450,
        facilities: ["stage", "sound_system"],
        accessibility_features: ["hearing_loop", "step_free_entrance"],
      }),
    ]);
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByText("2 venues are available, smallest first.")).toBeInTheDocument();
    const results = screen.getByRole("list", { name: "Available venues" });
    expect(within(results).getAllByRole("listitem").map((item) => item.getAttribute("aria-label"))).toEqual([
      "SCIS Seminar Room 2-1",
      "Mochtar Riady Auditorium",
    ]);
    const auditorium = within(results).getByRole("listitem", { name: "Mochtar Riady Auditorium" });
    expect(auditorium).toHaveTextContent("450");
    expect(auditorium).toHaveTextContent("Stage, Sound system");
    expect(auditorium).toHaveTextContent("Hearing loop, Step-free entrance");
    expect(within(results).getByRole("listitem", { name: "SCIS Seminar Room 2-1" })).toHaveTextContent("None listed");
  });

  it("labels the results with the criteria the API applied, in Singapore date format", async () => {
    nextSearchResult([seedVenue({ name: "Free room" })]);
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));
    await screen.findByRole("list", { name: "Available venues" });

    expect(criteriaLines()).toEqual(["Date: Sat, Oct 10", "Time: 10:00–12:00", "Expected attendance: 30"]);
  });

  it("says the results are out of date once the form changes, until searched again", async () => {
    nextSearchResult([seedVenue({ name: "Free room" })]);
    const user = userEvent.setup();
    await openVenues(user);
    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));
    await screen.findByRole("list", { name: "Available venues" });
    const stale = "You've changed the search. Press Search venues to update these results.";
    expect(screen.queryByText(stale)).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText("Expected attendance"));
    await user.type(screen.getByLabelText("Expected attendance"), "300");

    expect(screen.getByText(stale)).toBeInTheDocument();
    // The criteria still describe the results on screen, not the edited form.
    expect(criteriaLines()).toContain("Expected attendance: 30");

    await user.click(screen.getByRole("button", { name: "Search venues" }));
    await screen.findByText("Expected attendance: 300");
    expect(screen.queryByText(stale)).not.toBeInTheDocument();
  });

  it("says no matching venues and lists the criteria applied (AC 7)", async () => {
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user, { attendees: "500" });
    await user.type(screen.getByLabelText("Location"), "Library");
    await user.click(searchForm().getByRole("checkbox", { name: "Wi-Fi" }));
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByText("No matching venues.")).toBeInTheDocument();
    expect(criteriaLines()).toEqual([
      "Date: Sat, Oct 10",
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

  it("marks the field an INVALID_VENUE_SEARCH names, with the API's message", async () => {
    server.use(
      http.get("http://api.test/api/v1/venues/available", () =>
        HttpResponse.json(
          {
            code: "INVALID_VENUE_SEARCH",
            fields: ["attendees"],
            errors: { attendees: "Expected attendance must be a whole number." },
          },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user, { attendees: "1.5" });
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Review the fields marked below");
    const attendance = screen.getByLabelText("Expected attendance");
    expect(attendance).toHaveAttribute("aria-invalid", "true");
    expect(attendance).toHaveAccessibleDescription("Expected attendance must be a whole number.");
  });

  it("explains a 403 in search's own words", async () => {
    server.use(
      http.get("http://api.test/api/v1/venues/available", () =>
        HttpResponse.json({ code: "FORBIDDEN" }, { status: 403 }),
      ),
    );
    const user = userEvent.setup();
    await openVenues(user);

    await fillCore(user);
    await user.click(screen.getByRole("button", { name: "Search venues" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Only coordinators and venue staff can search for available venues.");
    expect(alert).not.toHaveTextContent("change venues");
  });

  it("clears the form and results", async () => {
    nextSearchResult([seedVenue({ name: "Free room" })]);
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
