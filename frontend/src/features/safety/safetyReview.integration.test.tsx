import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import {
  COORDINATOR_ID,
  SAFETY_OFFICER_ID,
  callsTo,
  db,
  seedBooking,
  seedEquipmentEvent,
  seedEquipmentLine,
  seedEquipmentType,
  seedRequest,
  seedVenue,
  server,
  startMockBackend,
} from "../../test/server";

// US30a (SCRUM-99): the real App against the fake backend. Which events are ready, and what a review
// must hold, is the API's rule (backend/tests/safety/test_safety_review.py); here, what the screens show,
// offer and send.
startMockBackend();

const CASEY = { id: COORDINATOR_ID, name: "Casey Tan" };
const KEYS = [
  "attendance_capacity",
  "layout",
  "emergency_access",
  "accessibility",
  "equipment_placement",
  "crowd_movement",
  "venue_restrictions",
];

type User = ReturnType<typeof userEvent.setup>;

function seedReadyEvent(overrides = {}) {
  const request = seedRequest({
    name: "Alumni night",
    status: "approved",
    coordinator: CASEY,
    accessibility_needs: "Step-free access",
    ...overrides,
  });
  seedBooking(request, seedVenue({ name: "SCIS Seminar Room 2-1" }), { status: "approved", expected_attendees: 40 });
  return request;
}

async function openSafetyQueue(user: User) {
  setDevRole("safety_officer");
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Safety reviews" }));
}

async function openEvent(user: User, name = "Alumni night") {
  await openSafetyQueue(user);
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
  await screen.findByRole("heading", { name: "Safety review" });
}

// The seven checklist items are the groups of radios; the areas affected (US30b) are a group of checkboxes.
function checklistGroups() {
  return screen.getAllByRole("group").filter((group) => within(group).queryAllByRole("radio").length > 0);
}

async function answerAll(user: User, result: "Satisfactory" | "Issue" = "Satisfactory") {
  for (const group of checklistGroups()) {
    await user.click(within(group).getByRole("radio", { name: result }));
  }
}

beforeEach(() => setDevRole("safety_officer"));

describe("Safety Officer's queue (US30a AC 1)", () => {
  it("lists events whose venue and equipment are approved and that have no decision yet", async () => {
    seedReadyEvent();
    seedRequest({ name: "No venue yet", status: "approved", coordinator: CASEY });
    const waiting = seedRequest({ name: "Equipment pending", status: "approved", coordinator: CASEY });
    seedBooking(waiting, seedVenue({ name: "Auditorium" }), { status: "approved", expected_attendees: 40 });
    seedEquipmentLine(seedEquipmentEvent({ id: waiting.id }), seedEquipmentType("Projector"), { status: "pending" });
    seedReadyEvent({ name: "Already approved", safety_approved_at: "2026-10-02T03:00:00Z" });
    const user = userEvent.setup();

    await openSafetyQueue(user);

    expect(await screen.findByRole("button", { name: /Alumni night/ })).toHaveTextContent("SCIS Seminar Room 2-1");
    expect(screen.queryByRole("button", { name: /No venue yet/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Equipment pending/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Already approved/ })).not.toBeInTheDocument();
  });

  it("says so when nothing is waiting", async () => {
    const user = userEvent.setup();

    await openSafetyQueue(user);

    expect(await screen.findByText("No events are waiting for a safety review.")).toBeInTheDocument();
  });
});

describe("Safety Officer reviews an event (US30a AC 2, 9)", () => {
  it("shows the event's details, venues and equipment, and the seven checklist items", async () => {
    const request = seedReadyEvent();
    const line = seedEquipmentLine(seedEquipmentEvent({ id: request.id }), seedEquipmentType("Projector"), { status: "approved", quantity: 2 });
    line.reservation = { quantity: 2, reserved_by_user_id: "tech-support-id", reserved_at: "2026-10-02T03:00:00Z", released_because_event_cancelled: false };
    const user = userEvent.setup();

    await openEvent(user);

    expect(within(screen.getByRole("region", { name: "Event details" })).getByText("Step-free access")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Venue SCIS Seminar Room 2-1" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Equipment" })).getByText(/2 × Projector/)).toBeInTheDocument();
    expect(checklistGroups()).toHaveLength(7);
    expect(screen.getByRole("group", { name: "Emergency access" })).toBeInTheDocument();
    // Nothing about the organiser or the request's history is shown (AC 9).
    expect(screen.queryByText(/organiser-id/i)).not.toBeInTheDocument();
  });

  it("approves with every item satisfactory, and the event leaves the queue (AC 3, 6)", async () => {
    const request = seedReadyEvent();
    const user = userEvent.setup();
    await openEvent(user);

    await answerAll(user);
    await user.type(screen.getByLabelText(/^Comments for the coordinator/), "All clear.");
    await user.type(screen.getByLabelText(/^Internal notes/), "Checked the floor plan.");
    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("heading", { name: "Safety approved" })).toBeInTheDocument();
    const [call] = callsTo("POST", `/api/v1/safety-reviews/${request.id}`);
    expect(call.headers.get("X-User-Id")).toBe(SAFETY_OFFICER_ID);
    const sent = call.body as { outcome: string; comments: string; internal_notes: string; checklist: Record<string, unknown> };
    expect([sent.outcome, sent.comments, sent.internal_notes]).toEqual(["approved", "All clear.", "Checked the floor plan."]);
    expect(Object.keys(sent.checklist)).toEqual(KEYS);
    expect(db.requests.find((r) => r.id === request.id)?.safety_approved_at).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "Back to safety reviews" }));
    expect(await screen.findByText("No events are waiting for a safety review.")).toBeInTheDocument();
  });

  it("needs every item answered, and comments to reject (AC 2, 4)", async () => {
    const request = seedReadyEvent();
    const user = userEvent.setup();
    await openEvent(user);

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Answer every checklist item");
    expect(callsTo("POST", `/api/v1/safety-reviews/${request.id}`)).toHaveLength(0);

    await answerAll(user);
    await user.click(screen.getByRole("button", { name: "Reject safety arrangement" }));
    expect(screen.getByLabelText(/^Comments for the coordinator/)).toHaveAttribute("aria-invalid", "true");
    expect(callsTo("POST", `/api/v1/safety-reviews/${request.id}`)).toHaveLength(0);
  });

  it("rejects the safety arrangement with comments, and the event stays in planning (AC 4)", async () => {
    const request = seedReadyEvent({ status: "planning" });
    const user = userEvent.setup();
    await openEvent(user);

    await answerAll(user);
    await user.click(within(screen.getByRole("group", { name: "Emergency access" })).getByRole("radio", { name: "Issue" }));
    await user.type(screen.getByLabelText("Emergency access comment"), "Only one exit is clear.");
    await user.type(screen.getByLabelText(/^Comments for the coordinator/), "Add a second exit.");
    await user.click(screen.getByRole("button", { name: "Reject safety arrangement" }));

    expect(await screen.findByRole("heading", { name: "Safety arrangement rejected" })).toBeInTheDocument();
    expect(screen.getByText(/stays in planning/)).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Checklist issues" })).getByText("Emergency access: Only one exit is clear.")).toBeInTheDocument();
    expect(db.requests.find((r) => r.id === request.id)).toMatchObject({ status: "planning", safety_approved_at: null });
  });

  it("explains an approval the API refuses because an item is flagged", async () => {
    seedReadyEvent();
    const user = userEvent.setup();
    await openEvent(user);
    await answerAll(user);
    server.use(
      http.post("*/api/v1/safety-reviews/:id", () =>
        HttpResponse.json({ code: "CHECKLIST_HAS_ISSUES", fields: ["checklist.layout"] }, { status: 422 }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("An item is marked Issue, so this can't be approved");
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });
});

describe("Organiser and Coordinator read the outcome (US30a AC 4, 7)", () => {
  function seedRejected(name = "Alumni night") {
    const request = seedReadyEvent({ name, status: "planning" });
    db.safetyReviews.push({
      id: "review-1",
      event_id: request.id,
      outcome: "rejected",
      areas: null,
      checklist: Object.fromEntries(KEYS.map((key) => [key, { result: key === "emergency_access" ? "issue" : "satisfactory", comment: key === "emergency_access" ? "Only one exit is clear." : null }])) as never,
      comments: "Add a second exit.",
      internal_notes: "Venue has a history of blocked exits.",
      reviewer: { id: SAFETY_OFFICER_ID, name: "Sam Safety" },
      created_at: "2026-10-04T03:00:00Z",
    });
    return request;
  }

  it("shows the organiser the outcome and the comments, never the internal notes", async () => {
    seedRejected();
    setDevRole("organiser");
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));

    await user.click(await screen.findByRole("button", { name: /Alumni night/ }));

    const outcome = await screen.findByRole("region", { name: "Safety review" });
    expect(outcome).toHaveTextContent("Safety arrangement rejected");
    expect(outcome).toHaveTextContent("Comments: Add a second exit.");
    expect(within(outcome).getByText("Emergency access: Only one exit is clear.")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("blocked exits");
    expect(within(outcome).queryByRole("button")).not.toBeInTheDocument();
  });

  it("lets the coordinator send a rejected arrangement back for another review (AC 4)", async () => {
    const request = seedRejected();
    setDevRole("coordinator");
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
    await user.click(await screen.findByRole("button", { name: /Alumni night/ }));

    const readiness = await screen.findByRole("list", { name: "Readiness" });
    expect(within(readiness).getByText(/Rejected by the Safety Officer: Add a second exit\./)).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Send for another review" }));

    expect(await screen.findByText("Sent for another safety review.")).toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/event-requests/${request.id}/safety-review-request`)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Send for another review" })).not.toBeInTheDocument();
  });

  it("shows nothing on an event that is still at the request stage", async () => {
    seedRequest({ name: "Still under review", status: "under_review", coordinator: CASEY });
    setDevRole("coordinator");
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
    await user.click(await screen.findByRole("button", { name: /Still under review/ }));
    await screen.findByRole("heading", { name: "Review request" });

    expect(screen.queryByRole("region", { name: "Safety review" })).not.toBeInTheDocument();
    expect(callsTo("GET", /safety-reviews$/)).toHaveLength(0);
  });
});

// US30b (SCRUM-100): request changes, with comments and the areas affected; the coordinator marks them done.
describe("Safety Officer requests changes (US30b AC 1, 2)", () => {
  it("TC-US30B-31: offers Request changes with the five areas to tick", async () => {
    seedReadyEvent();
    const user = userEvent.setup();

    await openEvent(user);

    const areas = screen.getByRole("group", { name: /Areas affected/ });
    expect(within(areas).getAllByRole("checkbox").map((box) => box.closest("label")?.textContent)).toEqual([
      "Venue", "Layout", "Equipment", "Accessibility", "Other",
    ]);
    expect(screen.getByRole("button", { name: "Request changes" })).toBeInTheDocument();
  });

  it("TC-US30B-32: needs comments and at least one area, and sends nothing without them", async () => {
    seedReadyEvent();
    const user = userEvent.setup();
    await openEvent(user);
    await answerAll(user);

    await user.click(screen.getByRole("button", { name: "Request changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Tick at least one area when requesting changes");
    await user.type(screen.getByLabelText("Comments for the coordinator and organiser"), "Widen the aisles.");
    await user.click(screen.getByRole("button", { name: "Request changes" }));
    await user.click(within(screen.getByRole("group", { name: /Areas affected/ })).getByRole("checkbox", { name: "Layout" }));
    await user.clear(screen.getByLabelText("Comments for the coordinator and organiser"));
    await user.click(screen.getByRole("button", { name: "Request changes" }));

    expect(screen.getByLabelText("Comments for the coordinator and organiser")).toBeInvalid();
    expect(callsTo("POST", /safety-reviews\//)).toHaveLength(0);
  });

  it("TC-US30A-50: says an Approved event stays Approved after a rejection, not planning", async () => {
    seedReadyEvent();
    const user = userEvent.setup();
    await openEvent(user);
    await answerAll(user);
    await user.click(within(screen.getByRole("group", { name: "Emergency access" })).getByRole("radio", { name: "Issue" }));
    await user.type(screen.getByLabelText(/^Comments for the coordinator/), "Add a second exit.");

    await user.click(screen.getByRole("button", { name: "Reject safety arrangement" }));

    expect(await screen.findByRole("heading", { name: "Safety arrangement rejected" })).toBeInTheDocument();
    expect(screen.getByText(/stays in approved\./)).toBeInTheDocument();
    expect(screen.queryByText(/stays in planning/)).not.toBeInTheDocument();
  });

  it("TC-US30B-37: says a Planning event stays in planning after a request for changes", async () => {
    seedReadyEvent({ status: "planning" });
    const user = userEvent.setup();
    await openEvent(user);
    await answerAll(user);
    await user.click(within(screen.getByRole("group", { name: /Areas affected/ })).getByRole("checkbox", { name: "Layout" }));
    await user.type(screen.getByLabelText(/^Comments for the coordinator/), "Widen the aisles.");

    await user.click(screen.getByRole("button", { name: "Request changes" }));

    expect(await screen.findByRole("heading", { name: "Changes requested" })).toBeInTheDocument();
    expect(screen.getByText(/stays in planning with the areas below marked for review/)).toBeInTheDocument();
  });

  it("TC-US30B-33: sends the outcome, comments and ticked areas, and shows what was sent", async () => {
    const request = seedReadyEvent();
    const user = userEvent.setup();
    await openEvent(user);
    await answerAll(user);
    await user.click(within(screen.getByRole("group", { name: "Room layout" })).getByRole("radio", { name: "Issue" }));
    const areas = screen.getByRole("group", { name: /Areas affected/ });
    await user.click(within(areas).getByRole("checkbox", { name: "Venue" }));
    await user.click(within(areas).getByRole("checkbox", { name: "Equipment" }));
    await user.type(screen.getByLabelText("Comments for the coordinator and organiser"), "Move the stage back.");
    await user.type(screen.getByLabelText(/^Internal notes/), "Second time.");

    await user.click(screen.getByRole("button", { name: "Request changes" }));

    expect(await screen.findByRole("heading", { name: "Changes requested" })).toBeInTheDocument();
    const [call] = callsTo("POST", `/api/v1/safety-reviews/${request.id}`);
    expect(call.body).toMatchObject({ outcome: "changes_requested", areas: ["venue", "equipment"], comments: "Move the stage back.", internal_notes: "Second time." });
    const listed = screen.getByRole("list", { name: "Areas to review" });
    expect(within(listed).getAllByRole("listitem").map((item) => item.textContent)).toEqual(["Venue", "Equipment"]);
    // The demo is Approved, so it says approved; an event that is Planning says planning (TC-US30B-37).
    expect(screen.getByText(/stays in approved with the areas below marked for review/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to safety reviews" }));
    expect(await screen.findByText("No events are waiting for a safety review.")).toBeInTheDocument();
  });
});

describe("Coordinator and Organiser read the request for changes (US30b AC 2, 3, 4)", () => {
  function seedChanges() {
    const request = seedReadyEvent({ status: "planning" });
    db.safetyReviews.push({
      id: "review-changes",
      event_id: request.id,
      outcome: "changes_requested",
      areas: ["venue", "layout"],
      checklist: Object.fromEntries(KEYS.map((key) => [key, { result: key === "layout" ? "issue" : "satisfactory", comment: key === "layout" ? "Aisles too narrow" : null }])) as never,
      comments: "Widen the aisles.",
      internal_notes: "Second time this layout has come up.",
      reviewer: { id: SAFETY_OFFICER_ID, name: "Sam Safety" },
      created_at: "2026-10-04T03:00:00Z",
    });
    return request;
  }

  async function openAs(role: "organiser" | "coordinator", user: User) {
    setDevRole(role);
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
    await user.click(await screen.findByRole("button", { name: /Alumni night/ }));
  }

  it("TC-US30B-34: the organiser reads the areas and comments, never the internal notes", async () => {
    seedChanges();
    const user = userEvent.setup();

    await openAs("organiser", user);

    const outcome = await screen.findByRole("region", { name: "Safety review" });
    expect(outcome).toHaveTextContent("Changes requested");
    expect(within(within(outcome).getByRole("list", { name: "Areas to review" })).getAllByRole("listitem").map((i) => i.textContent)).toEqual(["Venue", "Layout"]);
    expect(outcome).toHaveTextContent("Comments: Widen the aisles.");
    expect(within(outcome).getByText("Room layout: Aisles too narrow")).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("Second time");
    expect(within(outcome).queryByRole("button")).not.toBeInTheDocument();
  });

  it("TC-US30B-35: the coordinator sees it on the readiness list and marks the changes done", async () => {
    const request = seedChanges();
    const user = userEvent.setup();
    await openAs("coordinator", user);

    const readiness = await screen.findByRole("list", { name: "Readiness" });
    expect(within(readiness).getByText(/The Safety Officer asked for changes to Venue, Layout: Widen the aisles\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm event" })).toBeDisabled();
    await user.click(await screen.findByRole("button", { name: "Mark changes done" }));

    expect(await screen.findByText("Sent for another safety review.")).toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/event-requests/${request.id}/safety-review-request`)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Mark changes done" })).not.toBeInTheDocument();
  });

  it("TC-US30B-36: once marked done the event is back in the Safety Officer's queue, and the earlier review stays in its history", async () => {
    seedChanges();
    db.safetyResent[db.requests[0].id] = true;
    const user = userEvent.setup();

    await openEvent(user);

    const earlier = screen.getByRole("region", { name: "Earlier reviews" });
    expect(earlier).toHaveTextContent("Changes requested");
    expect(earlier).toHaveTextContent("Areas to review: Venue, Layout");
    expect(earlier).toHaveTextContent("Internal notes: Second time this layout has come up.");
  });
});
