import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { callsTo, seedManagedEvent, server, startMockBackend } from "../../test/server";

// US28 (SCRUM-96): the real App and EventRegistrationsPage against the fake backend. The fake returns
// what `seedManagedEvent` seeds, so these tests check what the screen sends and how it shows the
// answer. Who may see an event (AC 1) and which rows a filter returns (AC 4, 5) are the API's rules,
// tested in backend/tests/registration/test_event_registrations.py, not here.
startMockBackend();

beforeEach(() => setDevRole("organiser"));

type User = ReturnType<typeof userEvent.setup>;

async function openRegistrations(user: User) {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Registrations" }));
  return screen.findByRole("heading", { name: "Event registrations" });
}

function bootcamp() {
  return seedManagedEvent({
    totals: { confirmed: 2, waitlisted: 1, offered: 0, seats_remaining: 0 },
    registration_fields: [
      { field_key: "dietary", label: "Dietary requirements", field_type: "text", options: null, required: false },
    ],
    registrations: [
      {
        registration_id: "r-1",
        attendee_name: "Mei Tan",
        attendee_email: "mei.tan.2024@smu.edu.sg",
        status: "confirmed",
        registered_at: "2026-10-01T01:00:00Z",
        waitlist_position: null,
        offer_expires_at: null,
        answers: { dietary: "vegetarian" },
      },
      {
        registration_id: "r-2",
        attendee_name: null,
        attendee_email: "sofia.lim.2024@smu.edu.sg",
        status: "waitlisted",
        registered_at: "2026-10-01T02:00:00Z",
        waitlist_position: 1,
        offer_expires_at: null,
        answers: {},
      },
    ],
  });
}

function lastRegistrationsCall() {
  return callsTo("GET", /^\/api\/v1\/events\/[^/]+\/registrations$/).at(-1)!;
}

describe("event registrations (US28)", () => {
  it("lists the events the organiser manages, as the organiser", async () => {
    const user = userEvent.setup();
    bootcamp();
    await openRegistrations(user);

    const events = await screen.findByRole("region", { name: "Events you manage" });
    expect(within(events).getByRole("button", { name: /Design Sprint Bootcamp/ })).toBeInTheDocument();
    expect(callsTo("GET", "/api/v1/me/managed-events")[0].headers.get("X-User-Id")).toBe("organiser-id");
  });

  it("shows the totals and each registrant's details and answers (AC 2, 3)", async () => {
    const user = userEvent.setup();
    const managed = bootcamp();
    await openRegistrations(user);

    await user.click(await screen.findByRole("button", { name: /Design Sprint Bootcamp/ }));

    const totals = within(await screen.findByLabelText("Registration totals"));
    expect(totals.getByText("Confirmed").nextSibling?.textContent).toBe("2");
    expect(totals.getByText("Waitlisted").nextSibling?.textContent).toBe("1");
    expect(totals.getByText("Offered a place").nextSibling?.textContent).toBe("0");
    expect(totals.getByText("Places left").nextSibling?.textContent).toBe("0");

    const table = screen.getByRole("table", { name: "Registrants" });
    expect(within(table).getByRole("columnheader", { name: "Dietary requirements" })).toBeInTheDocument();
    const [, mei, sofia] = within(table).getAllByRole("row");
    expect(within(mei).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "Mei Tan",
      "mei.tan.2024@smu.edu.sg",
      "Confirmed",
      "Thu, Oct 1, 9:00 AM",
      "—",
      "vegetarian",
    ]);
    expect(within(sofia).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "—",
      "sofia.lim.2024@smu.edu.sg",
      "Waitlisted",
      "Thu, Oct 1, 10:00 AM",
      "1",
      "—",
    ]);
    // Active rows only by default (AC 5): no filter sent.
    expect(lastRegistrationsCall().path).toBe(`/api/v1/events/${managed.event.id}/registrations`);
    expect(lastRegistrationsCall().url.search).toBe("");
  });

  it("sends the status filter and the Show all toggle (AC 4, 5)", async () => {
    const user = userEvent.setup();
    bootcamp();
    await openRegistrations(user);
    await user.click(await screen.findByRole("button", { name: /Design Sprint Bootcamp/ }));
    await screen.findByRole("table", { name: "Registrants" });

    await user.click(screen.getByRole("checkbox", { name: /Show all/ }));
    await screen.findByRole("table", { name: "Registrants" });
    expect(lastRegistrationsCall().url.searchParams.get("show_all")).toBe("true");

    await user.selectOptions(screen.getByLabelText("Status"), "withdrawn");
    await screen.findByRole("table", { name: "Registrants" });
    expect(Object.fromEntries(lastRegistrationsCall().url.searchParams)).toEqual({ status: "withdrawn" });
    // A status filter decides on its own, so Show all doesn't apply while one is chosen.
    expect(screen.getByRole("checkbox", { name: /Show all/ })).toBeDisabled();
  });

  it("keeps the filters on screen when a load fails, so a different filter retries", async () => {
    const user = userEvent.setup();
    bootcamp();
    await openRegistrations(user);
    await user.click(await screen.findByRole("button", { name: /Design Sprint Bootcamp/ }));
    await screen.findByRole("table", { name: "Registrants" });

    server.use(
      http.get("http://api.test/api/v1/events/:eventId/registrations", () => HttpResponse.json({}, { status: 500 }), {
        once: true,
      }),
    );
    await user.selectOptions(screen.getByLabelText("Status"), "waitlisted");

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be completed/);
    expect(screen.getByLabelText("Status")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Registrants" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Status"), "all");
    expect(await screen.findByRole("table", { name: "Registrants" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("goes back to the event list", async () => {
    const user = userEvent.setup();
    bootcamp();
    await openRegistrations(user);
    await user.click(await screen.findByRole("button", { name: /Design Sprint Bootcamp/ }));
    await screen.findByRole("heading", { level: 1, name: "Design Sprint Bootcamp" });

    await user.click(screen.getByRole("button", { name: "All events" }));

    expect(await screen.findByRole("region", { name: "Events you manage" })).toBeInTheDocument();
  });

  it("asks a coordinator's own list, with the coordinator's id", async () => {
    setDevRole("coordinator");
    const user = userEvent.setup();
    seedManagedEvent({}, ["organiser"]);
    const coordinated = seedManagedEvent({}, ["coordinator"]);
    coordinated.event.name = "Faculty Town Hall";
    await openRegistrations(user);

    const events = await screen.findByRole("region", { name: "Events you manage" });
    expect(within(events).getAllByRole("button").map((row) => row.textContent)).toEqual([
      expect.stringContaining("Faculty Town Hall"),
    ]);
    expect(callsTo("GET", "/api/v1/me/managed-events")[0].headers.get("X-User-Id")).toBe("coordinator-id");
  });

  it("says when there are no events yet", async () => {
    const user = userEvent.setup();
    await openRegistrations(user);

    expect(await screen.findByText(/No events to show yet/)).toBeInTheDocument();
  });

  it("isn't offered to venue staff", async () => {
    setDevRole("venue_staff");
    const user = userEvent.setup();
    render(<App />);

    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Registrations" }));

    expect(screen.getByText(/Registrations are for organisers and coordinators/)).toBeInTheDocument();
    expect(callsTo("GET", "/api/v1/me/managed-events")).toHaveLength(0);
  });
});
