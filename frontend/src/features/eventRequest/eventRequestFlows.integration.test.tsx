import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { callsTo, db, seedClarification, seedRequest, server, startMockBackend } from "../../test/server";

// The real App and event-request screens against the fake backend in test/server.ts.
startMockBackend();

beforeEach(() => setDevRole("organiser"));

async function openEventRequests(user: ReturnType<typeof userEvent.setup>) {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
}

async function actAs(user: ReturnType<typeof userEvent.setup>, role: "organiser" | "coordinator") {
  await user.selectOptions(screen.getByLabelText("Acting as"), role);
}

describe("organiser: event requests (US1)", () => {
  it("saves a partial draft, is told what's missing on submit, completes it and gets a reference", async () => {
    const user = userEvent.setup();
    await openEventRequests(user);
    expect(await screen.findByText("No requests yet.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Create request" }));
    await user.type(screen.getByLabelText("Event name"), "Neighbourhood planning workshop");
    await user.type(screen.getByLabelText("Event category"), "Workshop");
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Draft saved");
    expect(callsTo("POST", "/api/v1/event-requests")[0].headers.get("X-User-Id")).toBe("organiser-id");

    // Submitting saves first (PATCH, since the draft exists), then the 422 flags each field (SCRUM-46).
    await user.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Complete the fields marked below");
    const missing = screen.getByText("Fields to complete").parentElement!;
    expect(missing).toHaveTextContent("Purpose / description");
    expect(missing).toHaveTextContent("Expected attendees");
    expect(screen.getByLabelText("Purpose / description")).toHaveAttribute("aria-invalid", "true");
    expect(callsTo("PATCH", /^\/api\/v1\/event-requests\//)).toHaveLength(1);
    expect(db.requests[0].status).toBe("draft");

    // Typing in a flagged field clears its flag.
    await user.type(screen.getByLabelText("Purpose / description"), "Plan the next community event");
    expect(screen.getByLabelText("Purpose / description")).toHaveAttribute("aria-invalid", "false");

    // The date left in the picker is included without pressing Add date (deviation 10).
    await user.type(screen.getByLabelText("Preferred date"), "2026-11-20");
    await user.type(screen.getByLabelText("Preferred start time"), "09:30");
    await user.type(screen.getByLabelText("Preferred end time"), "11:30");
    await user.type(screen.getByLabelText("Expected attendees"), "32");
    await user.click(screen.getByRole("button", { name: "Submit request" }));

    expect(await screen.findByRole("heading", { level: 2, name: "Submission confirmed" })).toBeInTheDocument();
    expect(screen.getByText("ER-2026-000001")).toBeInTheDocument();
    expect(db.requests[0]).toMatchObject({ status: "submitted", preferred_dates: ["2026-11-20"], expected_attendees: 32 });

    await user.click(screen.getAllByRole("button", { name: "Back to my requests" })[0]);
    const row = await screen.findByRole("button", { name: /Neighbourhood planning workshop/ });
    expect(row).toHaveTextContent("submitted");
    expect(row).toHaveTextContent("ER-2026-000001");
  });

  it("adds and removes preferred dates as chips", async () => {
    const user = userEvent.setup();
    await openEventRequests(user);
    await user.click(await screen.findByRole("button", { name: "Create request" }));

    await user.type(screen.getByLabelText("Preferred date"), "2026-11-20");
    await user.click(screen.getByRole("button", { name: "Add date" }));
    await user.type(screen.getByLabelText("Preferred date"), "2026-11-21");
    await user.click(screen.getByRole("button", { name: "Add date" }));

    const chips = screen.getByRole("list", { name: "Selected preferred dates" });
    expect(within(chips).getAllByRole("listitem").map((li) => li.firstChild?.textContent)).toEqual([
      "2026-11-20",
      "2026-11-21",
    ]);

    await user.click(screen.getByRole("button", { name: "Remove 2026-11-20" }));
    expect(within(chips).getAllByRole("listitem")).toHaveLength(1);
  });

  it("reopens a draft with its saved values and keeps registration_required = false distinct (TC-US1-03)", async () => {
    const draft = seedRequest({ name: "Saved draft", expected_attendees: 12, registration_required: false });
    const user = userEvent.setup();
    await openEventRequests(user);

    await user.click(await screen.findByRole("button", { name: /Saved draft/ }));

    expect(await screen.findByLabelText("Event name")).toHaveValue("Saved draft");
    expect(screen.getByLabelText("Expected attendees")).toHaveValue(12);
    expect(screen.getByLabelText("Attendee registration")).toHaveValue("false");
    expect(callsTo("GET", `/api/v1/event-requests/${draft.id}`)).toHaveLength(1);
  });

  it("shows a submitted request's reference instead of the form (TC-US1-11)", async () => {
    seedRequest({ name: "Already sent", status: "submitted" });
    const user = userEvent.setup();
    await openEventRequests(user);

    await user.click(await screen.findByRole("button", { name: /Already sent/ }));
    expect(await screen.findByRole("heading", { level: 2, name: "Submission confirmed" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Event name")).not.toBeInTheDocument();
  });

  it("explains a missing organiser id (VITE_DEV_USER_ID)", async () => {
    server.use(
      http.get("http://api.test/api/v1/me/event-requests", () =>
        HttpResponse.json({ code: "UNAUTHENTICATED" }, { status: 401 }),
      ),
    );
    const user = userEvent.setup();
    await openEventRequests(user);
    expect(await screen.findByRole("alert")).toHaveTextContent("Set VITE_DEV_USER_ID");
  });
});

describe("coordinator: review queue and clarification (US8a)", () => {
  it("sends a clarification on chosen sections and the request moves to awaiting clarification", async () => {
    const request = seedRequest({ name: "Clarification workshop", status: "submitted", expected_attendees: 40 });
    const user = userEvent.setup();
    await openEventRequests(user);
    await actAs(user, "coordinator");

    expect(await screen.findByRole("heading", { name: "Requests to review" })).toBeInTheDocument();
    expect(callsTo("GET", "/api/v1/event-requests")[0].headers.get("X-User-Id")).toBe("coordinator-id");
    await user.click(await screen.findByRole("button", { name: /Clarification workshop/ }));

    // The request's values are shown under their sections.
    expect(await screen.findByRole("heading", { name: "Review request" })).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("14:00")).toBeInTheDocument();

    // Nothing chosen: both inputs are flagged (TC-US8-03).
    await user.click(screen.getByRole("button", { name: "Send clarification request" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose at least one section");
    expect(screen.getByLabelText("Comment for the organiser")).toHaveAttribute("aria-invalid", "true");

    // Ticked out of order, sent in D13's order.
    await user.click(screen.getByRole("checkbox", { name: "Room layout" }));
    await user.click(screen.getByRole("checkbox", { name: "Attendance" }));
    await user.type(screen.getByLabelText("Comment for the organiser"), "Final headcount and layout?");
    await user.click(screen.getByRole("button", { name: "Send clarification request" }));

    expect(await screen.findByRole("heading", { level: 2, name: "Clarification request sent" })).toBeInTheDocument();
    expect(screen.getByText("awaiting clarification")).toBeInTheDocument();
    const sent = callsTo("POST", `/api/v1/event-requests/${request.id}/clarifications`);
    expect(sent.at(-1)!.body).toEqual({ sections: ["attendance", "layout"], comment: "Final headcount and layout?" });
    expect(within(screen.getByRole("list", { name: "Sections sent" })).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "Attendance",
      "Room layout",
    ]);
  });

  it("disables the form for a request that can't take a clarification (D15)", async () => {
    seedRequest({ name: "Waiting on organiser", status: "awaiting_clarification" });
    const user = userEvent.setup();
    setDevRole("coordinator");
    await openEventRequests(user);

    await user.click(await screen.findByRole("button", { name: /Waiting on organiser/ }));
    expect(await screen.findByText(/This one is awaiting clarification/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Attendance" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Send clarification request" })).not.toBeInTheDocument();
  });

  it("shows an empty queue", async () => {
    seedRequest({ name: "Still a draft" });
    setDevRole("coordinator");
    const user = userEvent.setup();
    await openEventRequests(user);
    expect(await screen.findByText("No submitted requests to review.")).toBeInTheDocument();
  });
});

describe("organiser answers, coordinator reads the thread (US8c, US8d)", () => {
  it("answers the open question, and the coordinator sees question then answer", async () => {
    const request = seedRequest({ name: "Clarification workshop", status: "awaiting_clarification" });
    seedClarification(request, { sections: ["attendance", "layout"], comment: "Final headcount and layout?" });
    const user = userEvent.setup();
    await openEventRequests(user);

    const row = await screen.findByRole("button", { name: /Clarification workshop/ });
    expect(row).toHaveTextContent("awaiting clarification");
    await user.click(row);

    expect(await screen.findByRole("heading", { name: "Clarification requested" })).toBeInTheDocument();
    expect(screen.getByText("Final headcount and layout?")).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Sections in question" })).toHaveTextContent("AttendanceRoom layout");

    // Blank answer is flagged (TC-US8-22).
    await user.click(screen.getByRole("button", { name: "Send response" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Write a response before sending it.");
    expect(screen.getByLabelText("Your response")).toHaveAttribute("aria-invalid", "true");

    await user.type(screen.getByLabelText("Your response"), "40, in rows facing the stage.");
    await user.click(screen.getByRole("button", { name: "Send response" }));
    expect(await screen.findByRole("heading", { level: 2, name: "Response sent" })).toBeInTheDocument();
    expect(screen.getByText("under review")).toBeInTheDocument();

    // The coordinator's queue re-reads: under review, and the thread shows both messages.
    await actAs(user, "coordinator");
    const queued = await screen.findByRole("button", { name: /Clarification workshop/ });
    expect(queued).toHaveTextContent("under review");
    await user.click(queued);
    const round = within(
      await screen.findByRole("listitem", { name: "Round 1" }),
    );
    expect(round.getByText("Final headcount and layout?")).toBeInTheDocument();
    expect(round.getByText("40, in rows facing the stage.")).toBeInTheDocument();
  });

  it("shows earlier rounds above the open question in a later round (US8d AC 3)", async () => {
    const request = seedRequest({ name: "Two rounds", status: "awaiting_clarification" });
    seedClarification(request, { round: 1, comment: "Round one question" });
    seedClarification(request, { round: 1, kind: "response", comment: "Round one answer" });
    seedClarification(request, { round: 2, sections: ["equipment"], comment: "Which projector?" });
    const user = userEvent.setup();
    await openEventRequests(user);

    await user.click(await screen.findByRole("button", { name: /Two rounds/ }));

    const earlier = await screen.findByRole("region", { name: "Earlier rounds" });
    expect(earlier).toHaveTextContent("Round one question");
    expect(earlier).toHaveTextContent("Round one answer");
    expect(earlier).not.toHaveTextContent("Which projector?");
    expect(screen.getByText("Round 2", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Sections in question" })).toHaveTextContent("Equipment");
  });

  it("explains an answer to a round that's already closed (NO_OPEN_CLARIFICATION)", async () => {
    const request = seedRequest({ name: "Closed round", status: "awaiting_clarification" });
    seedClarification(request);
    server.use(
      http.post("http://api.test/api/v1/event-requests/:id/clarifications/response", () =>
        HttpResponse.json({ code: "NO_OPEN_CLARIFICATION", status: "under_review" }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    await openEventRequests(user);

    await user.click(await screen.findByRole("button", { name: /Closed round/ }));
    await user.type(await screen.findByLabelText("Your response"), "Late answer");
    await user.click(screen.getByRole("button", { name: "Send response" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This clarification has already been answered.");
  });
});
