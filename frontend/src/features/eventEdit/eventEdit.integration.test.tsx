import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { callsTo, seedCoordinatedEvent, server, startMockBackend } from "../../test/server";
import { toEditBody, formValues } from "./eventEditApi";

// US12 (SCRUM-15): the real App and EventsPage against the fake backend. Which fields are critical, the
// validation rules and the audit log are the API's (backend/tests/event/test_event_edits.py); these check
// what the screen sends and how it shows the answer.
startMockBackend();

beforeEach(() => setDevRole("coordinator"));

type User = ReturnType<typeof userEvent.setup>;

async function openEvent(user: User, name = "Event Planning Demo") {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Events" }));
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
  return screen.findByRole("heading", { name });
}

function lastEdit() {
  return callsTo("PATCH", /^\/api\/v1\/events\/[^/]+$/).at(-1)!;
}

describe("edit an event in planning (US12)", () => {
  it("TC-US12-21: Edit is enabled for a planning event and disabled otherwise (AC 1)", async () => {
    const user = userEvent.setup();
    seedCoordinatedEvent();
    seedCoordinatedEvent({ name: "Confirmed Showcase", status: "confirmed" });

    await openEvent(user);
    expect(screen.getByRole("button", { name: "Edit" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "All events" }));
    await user.click(await screen.findByRole("button", { name: /Confirmed Showcase/ }));
    await screen.findByRole("heading", { name: "Confirmed Showcase" });
    expect(screen.getByRole("button", { name: "Edit" })).toBeDisabled();
    expect(screen.getByText(/Only events in planning can be edited. This one is confirmed./)).toBeInTheDocument();
  });

  it("TC-US12-22: a non-critical change saves and shows at once, sending only what changed (AC 2)", async () => {
    const user = userEvent.setup();
    seedCoordinatedEvent();
    await openEvent(user);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.type(screen.getByLabelText("Equipment needs"), "Sticky notes");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Your changes are saved.");
    expect(lastEdit().body).toEqual({ equipment_needs: "Sticky notes" });
    const details = screen.getByRole("region", { name: "Event details" });
    expect(details).toHaveTextContent("Sticky notes");
    expect(screen.getByText("Planning", { selector: ".request-status" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /awaiting approval/ })).not.toBeInTheDocument();
  });

  it("TC-US12-23: a critical change keeps the old value and says it's awaiting approval (AC 3)", async () => {
    const user = userEvent.setup();
    seedCoordinatedEvent();
    await openEvent(user);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const capacity = screen.getByLabelText("Capacity");
    await user.clear(capacity);
    await user.type(capacity, "100");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("status")).toHaveTextContent("awaiting approval");
    expect(lastEdit().body).toEqual({ capacity: 100 });
    expect(screen.getByRole("region", { name: "Event details" })).toHaveTextContent("80");
    const pending = screen.getByRole("list", { name: "Changes awaiting approval" });
    expect(pending).toHaveTextContent("Capacity: 80 → 100");
    expect(pending).toHaveTextContent("Pending approval");
  });

  it("TC-US12-24: a refused save names the field and keeps the form open (AC 4)", async () => {
    const user = userEvent.setup();
    const event = seedCoordinatedEvent();
    server.use(
      http.patch(`http://api.test/api/v1/events/${event.id}`, () =>
        HttpResponse.json(
          { code: "INVALID_EVENT_EDIT", fields: ["end_at"], errors: { end_at: "End time must be after the start time." } },
          { status: 422 },
        ),
      ),
    );
    await openEvent(user);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const end = screen.getByLabelText("End time");
    await user.clear(end);
    await user.type(end, "09:00");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Nothing was saved.");
    expect(screen.getByLabelText("End time")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("End time must be after the start time.")).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Edit event" })).toBeInTheDocument();
  });

  it("TC-US12-25: History lists each saved field, newest first, with who and when (AC 5)", async () => {
    const user = userEvent.setup();
    seedCoordinatedEvent();
    await openEvent(user);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.type(screen.getByLabelText("Equipment needs"), "Pens");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await screen.findByRole("status");
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.clear(screen.getByLabelText("Room layout"));
    await user.type(screen.getByLabelText("Room layout"), "Cabaret");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await screen.findByText("Your changes are saved.");

    await user.click(screen.getByRole("tab", { name: "History" }));
    const rows = within(await screen.findByRole("table")).getAllByRole("row").slice(1);
    expect(rows.map((row) => within(row).getAllByRole("cell")[2].textContent)).toEqual(["Room layout", "Equipment needs"]);
    expect(rows[0]).toHaveTextContent("Casey Tan");
    expect(rows[0]).toHaveTextContent("coordinator-id");
    expect(within(rows[0]).getAllByRole("cell")[3]).toHaveTextContent("Classroom");
    expect(within(rows[0]).getAllByRole("cell")[4]).toHaveTextContent("Cabaret");
  });
});

describe("toEditBody", () => {
  it("sends the schedule as Singapore instants, and only the ends that changed", () => {
    const initial = formValues(seedCoordinatedEvent());
    expect(toEditBody(initial, { ...initial, endTime: "13:30" })).toEqual({ end_at: "2026-10-21T13:30:00+08:00" });
    expect(toEditBody(initial, { ...initial, date: "2026-10-22" })).toEqual({
      start_at: "2026-10-22T10:00:00+08:00",
      end_at: "2026-10-22T12:00:00+08:00",
    });
    expect(toEditBody(initial, { ...initial, expected_attendees: "1.5", name: " " })).toEqual({ expected_attendees: "1.5", name: null });
  });
});
