import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { callsTo, seedRequest, seedSession, server, startMockBackend } from "../../test/server";

// US15 (SCRUM-140): the real App and the organiser's request screens against the fake backend. The window, overlap
// and field rules are the API's (backend/tests/agenda/test_event_sessions_api.py); these check what the Agenda
// shows, sends and lists.
startMockBackend();

beforeEach(() => setDevRole("organiser"));

type User = ReturnType<typeof userEvent.setup>;

async function openAgenda(user: User, name = "Planning workshop") {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
  return screen.findByRole("region", { name: "Agenda" });
}

async function titles(agenda: HTMLElement) {
  const list = await within(agenda).findByRole("list", { name: "Sessions" });
  return within(list)
    .getAllByRole("listitem")
    .map((item) => within(item).getByRole("heading").textContent);
}

describe("the organiser builds their event's agenda (US15)", () => {
  it("TC-US15-13: adds a session, fixes a field error, edits one and deletes another, in time order throughout (AC 1, 2, 3, 5)", async () => {
    const user = userEvent.setup();
    const draft = seedRequest(); // a draft: 20 Nov, 14:00 to 16:00
    const welcome = seedSession(draft, { title: "Welcome", starts_at: "2026-11-20T14:00:00+08:00", ends_at: "2026-11-20T14:15:00+08:00" });
    const closing = seedSession(draft, {
      title: "Closing remarks",
      session_type: "other",
      speaker_name: "Olivia",
      starts_at: "2026-11-20T15:30:00+08:00",
      ends_at: "2026-11-20T16:00:00+08:00",
    });
    const agenda = await openAgenda(user);
    expect(await titles(agenda)).toEqual(["Welcome", "Closing remarks"]);

    // Add, with no speaker: the API's message shows on the field; nothing is listed yet.
    await user.click(within(agenda).getByRole("button", { name: "Add session" }));
    const form = within(agenda).getByRole("form", { name: "Session" });
    expect(within(form).getByLabelText("Date")).toHaveValue("2026-11-20");
    await user.type(within(form).getByLabelText("Title"), "Keynote");
    await user.type(within(form).getByLabelText("Start time"), "15:00");
    await user.type(within(form).getByLabelText("End time"), "15:30");
    await user.click(within(form).getByRole("button", { name: "Save session" }));
    const speaker = within(form).getByLabelText("Speaker or presenter");
    expect(speaker).toHaveAttribute("aria-invalid", "true");
    expect(form).toHaveTextContent("Name the speaker or presenter. Only a break has none.");
    expect(await titles(agenda)).toEqual(["Welcome", "Closing remarks"]);

    await user.type(speaker, "Dr Tan");
    await user.click(within(form).getByRole("button", { name: "Save session" }));
    expect(await within(agenda).findByText("Keynote")).toBeInTheDocument();
    expect(await titles(agenda)).toEqual(["Welcome", "Keynote", "Closing remarks"]);
    expect(callsTo("POST", `/api/v1/event-requests/${draft.id}/sessions`).at(-1)?.body).toEqual({
      title: "Keynote",
      session_type: "presentation",
      speaker_name: "Dr Tan",
      starts_at: "2026-11-20T15:00:00+08:00",
      ends_at: "2026-11-20T15:30:00+08:00",
    });

    // Edit: the closing remarks move earlier, and the list follows.
    await user.click(within(agenda).getByRole("button", { name: "Edit Closing remarks" }));
    const editing = within(agenda).getByRole("form", { name: "Session" });
    expect(within(editing).getByLabelText("Title")).toHaveValue("Closing remarks");
    await user.clear(within(editing).getByLabelText("Start time"));
    await user.type(within(editing).getByLabelText("Start time"), "14:15");
    await user.clear(within(editing).getByLabelText("End time"));
    await user.type(within(editing).getByLabelText("End time"), "14:45");
    await user.click(within(editing).getByRole("button", { name: "Save session" }));
    expect(await within(agenda).findByRole("button", { name: "Add session" })).toBeInTheDocument();
    expect(await titles(agenda)).toEqual(["Welcome", "Closing remarks", "Keynote"]);
    expect(callsTo("PATCH", `/api/v1/event-sessions/${closing.id}`)[0].body).toMatchObject({
      starts_at: "2026-11-20T14:15:00+08:00",
      ends_at: "2026-11-20T14:45:00+08:00",
    });

    // Delete another.
    await user.click(within(agenda).getByRole("button", { name: "Delete Welcome" }));
    expect(await within(agenda).findByRole("button", { name: "Delete Closing remarks" })).toBeInTheDocument();
    expect(await titles(agenda)).toEqual(["Closing remarks", "Keynote"]);
    expect(callsTo("DELETE", `/api/v1/event-sessions/${welcome.id}`)).toHaveLength(1);
  });

  it("TC-US15-13: a session saved with no times gets the API's message on Start time and End time (AC 2)", async () => {
    const user = userEvent.setup();
    const draft = seedRequest();
    const agenda = await openAgenda(user);

    await user.click(within(agenda).getByRole("button", { name: "Add session" }));
    const form = within(agenda).getByRole("form", { name: "Session" });
    await user.type(within(form).getByLabelText("Title"), "Keynote");
    await user.type(within(form).getByLabelText("Speaker or presenter"), "Dr Tan");
    await user.click(within(form).getByRole("button", { name: "Save session" }));

    expect(await within(agenda).findByRole("alert")).toHaveTextContent("Review the fields marked below");
    expect(within(form).getByLabelText("Start time")).toHaveAttribute("aria-invalid", "true");
    expect(within(form).getByLabelText("End time")).toHaveAttribute("aria-invalid", "true");
    expect(form).toHaveTextContent("Give the session's start time.");
    expect(form).toHaveTextContent("Give the session's end time.");
    expect(callsTo("POST", `/api/v1/event-requests/${draft.id}/sessions`)[0].body).toMatchObject({ starts_at: null, ends_at: null });
  });

  it("TC-US15-14: names the clashing session on an overlap (AC 4)", async () => {
    const user = userEvent.setup();
    const draft = seedRequest();
    server.use(
      http.post(`http://api.test/api/v1/event-requests/${draft.id}/sessions`, () =>
        HttpResponse.json(
          {
            code: "SESSION_OVERLAP",
            session: { id: "session-x", title: "Design sprint", starts_at: "2026-11-20T14:30:00+08:00", ends_at: "2026-11-20T15:30:00+08:00" },
          },
          { status: 409 },
        ),
      ),
    );
    const agenda = await openAgenda(user);

    await user.click(within(agenda).getByRole("button", { name: "Add session" }));
    const form = within(agenda).getByRole("form", { name: "Session" });
    await user.type(within(form).getByLabelText("Title"), "Industry panel");
    await user.selectOptions(within(form).getByLabelText("Session type"), "panel");
    await user.type(within(form).getByLabelText("Speaker or presenter"), "Three guests");
    await user.type(within(form).getByLabelText("Start time"), "15:00");
    await user.type(within(form).getByLabelText("End time"), "16:00");
    await user.click(within(form).getByRole("button", { name: "Save session" }));

    const alert = await within(agenda).findByRole("alert");
    expect(alert).toHaveTextContent("Design sprint");
    expect(alert).toHaveTextContent("2:30 PM – 3:30 PM");
    expect(within(agenda).getByRole("form", { name: "Session" })).toBeInTheDocument();
  });

  it("TC-US15-14: a submitted request's agenda is read-only (AC 1)", async () => {
    const user = userEvent.setup();
    const submitted = seedRequest({ status: "submitted" });
    seedSession(submitted);

    const agenda = await openAgenda(user);

    expect(await titles(agenda)).toEqual(["Opening keynote"]);
    expect(agenda).toHaveTextContent("The agenda can be changed while the request is a draft or in planning.");
    expect(within(agenda).queryByRole("button", { name: "Add session" })).not.toBeInTheDocument();
    expect(within(agenda).queryByRole("button", { name: /^(Edit|Delete) / })).not.toBeInTheDocument();
  });

  it("TC-US15-14: marks a session outside the event's current times (D94)", async () => {
    const user = userEvent.setup();
    const planning = seedRequest({ status: "planning", start_at: "2026-11-20T14:00:00+08:00", end_at: "2026-11-20T16:00:00+08:00" });
    seedSession(planning, { title: "Too early", starts_at: "2026-11-20T13:00:00+08:00", ends_at: "2026-11-20T13:30:00+08:00", outside_window: true });
    seedSession(planning, { title: "On time" });

    const agenda = await openAgenda(user);
    const items = within(await within(agenda).findByRole("list", { name: "Sessions" })).getAllByRole("listitem");

    expect(items[0]).toHaveTextContent("Too early");
    expect(items[0]).toHaveTextContent("Outside the event's times");
    expect(items[1]).not.toHaveTextContent("Outside the event's times");
    expect(within(agenda).getByRole("button", { name: "Add session" })).toBeInTheDocument();
  });
});
