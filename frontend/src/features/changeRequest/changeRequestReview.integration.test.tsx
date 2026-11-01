import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import {
  COORDINATOR_ID,
  callsTo,
  db,
  seedBooking,
  seedChangeRequest,
  seedCoordinatedEvent,
  seedEquipmentEvent,
  seedEquipmentLine,
  seedEquipmentType,
  seedRequest,
  seedReviewFlag,
  seedVenue,
  server,
  startMockBackend,
} from "../../test/server";

// US29b (SCRUM-143): the coordinator reviews, approves and rejects change requests, and works through the flags a
// significant change raises; the organiser sees each decision. What approving does is the API's rule, proven by
// backend/tests/event/test_change_request_decisions.py; here, what the screens show, send and refuse.
startMockBackend();

const CASEY = { id: COORDINATOR_ID, name: "Casey Tan" };
const LATER = { start_at: "2026-11-17T07:00:00+00:00", end_at: "2026-11-17T09:00:00+00:00" };

beforeEach(() => setDevRole("coordinator"));

type User = ReturnType<typeof userEvent.setup>;

/** A confirmed, safety-approved event with an approved booking and a reserved projector, like Change Request Demo. */
function seedDemo(overrides = {}) {
  const event = seedRequest({
    name: "Change Request Demo",
    status: "confirmed",
    coordinator: CASEY,
    start_at: "2026-11-17T06:00:00+00:00",
    end_at: "2026-11-17T08:00:00+00:00",
    expected_attendees: 20,
    safety_approved_at: "2026-10-01T01:00:00Z",
    confirmed_at: "2026-10-01T01:00:00Z",
    ...overrides,
  });
  seedBooking(event, seedVenue({ name: "Li Ka Shing Library Seminar Room 3-4" }), {
    status: "approved",
    expected_attendees: 20,
  });
  seedEquipmentLine(seedEquipmentEvent({ id: event.id, name: event.name ?? "" }), seedEquipmentType("Projector"), {
    status: "approved",
    quantity: 1,
    reservation: { quantity: 1, reserved_by_user_id: "tech", reserved_at: "2026-10-01T01:00:00Z", released_because_event_cancelled: false },
  });
  db.safetyReviews.push({
    id: "review-approved",
    event_id: event.id,
    outcome: "approved",
    checklist: {},
    comments: "The arrangement is safe as booked.",
    internal_notes: null,
    areas: null,
    reviewer: { id: "officer", name: "Sam Koh" },
    created_at: "2026-10-01T01:00:00Z",
  });
  return event;
}

function moveLater(event: ReturnType<typeof seedDemo>, overrides = {}) {
  return seedChangeRequest(event, {
    reason: "Our keynote speaker lands later.",
    changes: [
      { field: "start_at", old_value: event.start_at, new_value: LATER.start_at },
      { field: "end_at", old_value: event.end_at, new_value: LATER.end_at },
    ],
    ...overrides,
  });
}

async function openQueue(user: User) {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  return screen.findByRole("region", { name: /Change requests to review/ });
}

async function reviewFromQueue(user: User, eventName = "Change Request Demo") {
  const queue = await openQueue(user);
  const row = within(queue).getByRole("listitem", { name: new RegExp(eventName) });
  await user.click(within(row).getByRole("button", { name: "Review" }));
  await screen.findByRole("heading", { name: "Review request" });
  const panel = await screen.findByRole("region", { name: "Change requests for this event" });
  // Loaded: the requests are listed, not "Loading change requests…".
  await within(panel).findAllByRole("article");
  return panel;
}

describe("the coordinator reviews change requests (US29b)", () => {
  it("TC-US29B-26: lists pending requests on their events with event, requester, date and Significant (AC 1)", async () => {
    const user = userEvent.setup();
    const demo = seedDemo();
    moveLater(demo);
    const other = seedRequest({ name: "Board games night", status: "planning", coordinator: CASEY });
    seedChangeRequest(other, { reason: "A clearer title.", changes: [{ field: "name", old_value: other.name, new_value: "Games night" }] });

    const queue = await openQueue(user);

    expect(within(queue).getByRole("heading", { name: "Change requests to review (2)" })).toBeInTheDocument();
    const significant = within(queue).getByRole("listitem", { name: /Change Request Demo/ });
    expect(significant).toHaveTextContent("Olivia Organiser");
    expect(significant).toHaveTextContent("Requested");
    expect(significant).toHaveTextContent("Significant");
    expect(within(queue).getByRole("listitem", { name: /Board games night/ })).not.toHaveTextContent("Significant");
  });

  it("TC-US29B-26: has no section when nothing waits", async () => {
    const user = userEvent.setup();
    seedRequest({ name: "Quiet event", status: "submitted", coordinator: CASEY });
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
    await screen.findByRole("button", { name: /Quiet event/ });
    expect(screen.queryByRole("region", { name: /Change requests to review/ })).not.toBeInTheDocument();
  });

  it("TC-US29B-27: shows each field's current and proposed value, the reason, and what approving does (AC 1, 3, 6)", async () => {
    const user = userEvent.setup();
    moveLater(seedDemo());

    const panel = await reviewFromQueue(user);

    const rows = within(within(panel).getByRole("table", { name: "Requested changes" })).getAllByRole("row").slice(1);
    expect(rows.map((row) => within(row).getAllByRole("cell")[0].textContent)).toEqual(["Start time", "End time"]);
    expect(rows[0]).toHaveTextContent("2:00 PM");
    expect(rows[0]).toHaveTextContent("3:00 PM");
    expect(panel).toHaveTextContent("Reason: Our keynote speaker lands later.");
    const notice = within(panel).getByRole("note", { name: "What approving does" });
    expect(notice).toHaveTextContent("moves this event back to Planning");
    expect(notice).toHaveTextContent("flags 1 venue booking and 1 equipment reservation for review");
    expect(notice).toHaveTextContent("needs a new safety review");
  });

  it("TC-US29B-28: approves after a confirm step, then lists the flags until each is reviewed (AC 2, 3)", async () => {
    const user = userEvent.setup();
    const demo = seedDemo();
    const request = moveLater(demo);
    const panel = await reviewFromQueue(user);

    await user.click(within(panel).getByRole("button", { name: "Approve" }));
    expect(callsTo("POST", `/api/v1/change-requests/${request.id}/approve`)).toHaveLength(0);
    await user.click(within(panel).getByRole("button", { name: "Approve change" }));

    expect(await within(panel).findByRole("status")).toHaveTextContent("Approved. The event is now Planning.");
    expect(callsTo("POST", `/api/v1/change-requests/${request.id}/approve`)).toHaveLength(1);
    const flags = await screen.findByRole("region", { name: "Review after change" });
    const items = within(flags).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringContaining("Li Ka Shing Library Seminar Room 3-4"),
      expect.stringContaining("Projector × 1"),
    ]);
    expect(items[0]).toHaveTextContent("Start time, End time");
    const readiness = within(screen.getByRole("list", { name: "Readiness" }));
    expect(readiness.getByText("Review after change").closest("li")).toHaveTextContent("Outstanding");
    expect(screen.getByRole("button", { name: "Confirm event" })).toBeDisabled();

    for (const item of within(flags).getAllByRole("listitem")) {
      await user.click(within(item).getByRole("button", { name: "Mark reviewed" }));
      await user.type(within(item).getByLabelText("Note (optional)"), "Still fits.");
      await user.click(within(item).getByRole("button", { name: "Save review" }));
      expect(await within(item).findByText(/Reviewed by Casey Tan/)).toBeInTheDocument();
    }
    expect(db.reviewFlags.every((flag) => flag.cleared_at !== null)).toBe(true);
    const after = within(await screen.findByRole("list", { name: "Readiness" }));
    expect((await after.findByText("Review after change")).closest("li")).toHaveTextContent("Complete");
  });

  it("TC-US29B-28: a resolved flag reads as resolved and has nothing to mark", async () => {
    const user = userEvent.setup();
    const event = seedDemo({ status: "planning", confirmed_at: null, safety_approved_at: null });
    seedReviewFlag(event, { kind: "venue_booking", label: "VB-2026-000014 · Li Ka Shing Library Seminar Room 3-4", resolved: true, open: false });
    seedReviewFlag(event, { kind: "registrations", label: null, fields: ["start_at"] });
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
    await user.click(await screen.findByRole("button", { name: /Change Request Demo/ }));

    const items = within(await screen.findByRole("region", { name: "Review after change" })).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Registrations");
    expect(within(items[0]).getByRole("button", { name: "Mark reviewed" })).toBeInTheDocument();
    expect(items[1]).toHaveTextContent("Resolved: the booking is no longer live");
    expect(within(items[1]).queryByRole("button", { name: "Mark reviewed" })).not.toBeInTheDocument();
  });

  it("TC-US29B-28: History reads each kind of entry", async () => {
    setDevRole("coordinator");
    const user = userEvent.setup();
    const event = seedCoordinatedEvent({ name: "Event Planning Demo" });
    const who = { id: COORDINATOR_ID, name: "Casey Tan" };
    const entry = (action: string, field: string, previous: unknown, next: unknown) => ({
      id: `${action}-${field}`, field, previous_value: previous, new_value: next, user: who,
      created_at: "2026-10-01T02:00:00Z", change_request_id: "cr-1", change_request_status: "approved" as const, action,
    });
    db.history[event.id] = [
      entry("safety_approval_cleared", "safety_approval", { approved_at: "2026-10-01T01:00:00Z", approved_by: "officer" }, null),
      entry("confirmation_cleared", "confirmation", { confirmed_at: "2026-10-01T01:00:00Z", confirmed_by: COORDINATOR_ID }, null),
      entry("status_changed", "status", "confirmed", "planning"),
      entry("decided", "change_request", "pending_approval", { decision: "approved" }),
      entry("applied", "expected_attendees", 20, 30),
    ];
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Events" }));
    await user.click(await screen.findByRole("button", { name: /Event Planning Demo/ }));
    await user.click(await screen.findByRole("tab", { name: "History" }));

    const rows = within(await screen.findByRole("table")).getAllByRole("row").slice(1);
    const cells = (index: number) => within(rows[index]).getAllByRole("cell").map((cell) => cell.textContent);
    expect(cells(0)[2]).toContain("Safety approval cleared");
    expect(cells(0)[4]).toBe("Cleared");
    expect(cells(1)[2]).toContain("Confirmation cleared");
    expect(cells(2)[2]).toContain("Moved to Planning");
    expect([cells(2)[3], cells(2)[4]]).toEqual(["Confirmed", "Planning"]);
    expect(cells(3)[2]).toContain("Approved change");
    expect(cells(3)[4]).toBe("Approved");
    expect(cells(4)[2]).toContain("Applied");
    expect([cells(4)[3], cells(4)[4]]).toEqual(["20", "30"]);
  });

  it("TC-US29B-29: rejecting needs a reason, checked before anything is sent (AC 2)", async () => {
    const user = userEvent.setup();
    const request = moveLater(seedDemo());
    const panel = await reviewFromQueue(user);

    await user.click(within(panel).getByRole("button", { name: "Reject" }));
    await user.click(within(panel).getByRole("button", { name: "Reject change" }));
    const reason = within(panel).getByLabelText("Reason for rejecting");
    expect(reason).toHaveAttribute("aria-invalid", "true");
    expect(panel).toHaveTextContent("Give a reason for rejecting.");
    expect(callsTo("POST", `/api/v1/change-requests/${request.id}/reject`)).toHaveLength(0);

    await user.click(reason);
    await user.paste("x".repeat(1001));
    await user.click(within(panel).getByRole("button", { name: "Reject change" }));
    expect(panel).toHaveTextContent("The reason must be at most 1,000 characters.");
    expect(callsTo("POST", `/api/v1/change-requests/${request.id}/reject`)).toHaveLength(0);

    await user.clear(reason);
    await user.type(reason, "The library is booked that afternoon.");
    await user.click(within(panel).getByRole("button", { name: "Reject change" }));
    expect(await within(panel).findByRole("status")).toHaveTextContent("Rejected. The event keeps its current details.");
    expect(callsTo("POST", `/api/v1/change-requests/${request.id}/reject`).at(-1)!.body).toEqual({
      reason: "The library is booked that afternoon.",
    });
  });

  it.each([
    [
      { code: "CHANGE_REQUEST_STALE", fields: [{ field: "start_at", reason: "changed" }, { field: "end_at", reason: "not_at_this_stage" }] },
      "The event has changed since this was asked: Start time (changed since), End time (not open at this stage).",
    ],
    [{ code: "CHANGE_REQUEST_NOT_PENDING", status: "approved" }, "This request was already approved."],
    [{ code: "CHANGE_NOT_ALLOWED", status: "preparation" }, "Changes can't be approved while the event is in Preparation."],
  ])("TC-US29B-30: says why an approval was refused, and reloads the list (%o)", async (body, message) => {
    const user = userEvent.setup();
    moveLater(seedDemo());
    const panel = await reviewFromQueue(user);
    server.use(http.post("*/api/v1/change-requests/:id/approve", () => HttpResponse.json(body, { status: 409 })));
    const loads = callsTo("GET", "/api/v1/change-requests").length;

    await user.click(await within(panel).findByRole("button", { name: "Approve" }));
    await user.click(within(panel).getByRole("button", { name: "Approve change" }));

    expect(await within(panel).findByRole("alert")).toHaveTextContent(message);
    expect(callsTo("GET", "/api/v1/change-requests").length).toBeGreaterThan(loads);
  });

  it("TC-US29B-31: says a new safety review is needed once a change cleared the approval (AC 6)", async () => {
    const user = userEvent.setup();
    const request = moveLater(seedDemo());
    const panel = await reviewFromQueue(user);
    expect(screen.queryByText("A new safety review is needed.")).not.toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: "Approve" }));
    await user.click(within(panel).getByRole("button", { name: "Approve change" }));
    await within(panel).findByRole("status");

    const safety = await screen.findByRole("region", { name: "Safety review" });
    expect(await within(safety).findByText("A new safety review is needed.")).toBeInTheDocument();
    expect(safety).toHaveTextContent("A significant change was approved after the Safety Officer's approval");
    const readiness = within(screen.getByRole("list", { name: "Readiness" }));
    expect(readiness.getByText("Safety check").closest("li")).toHaveTextContent("Outstanding");
    expect(request.status).toBe("approved");
  });

  it("TC-US29B-31: an event still approved, or with changes requested, has no such notice (D99)", async () => {
    const user = userEvent.setup();
    seedDemo({ name: "Still approved" });
    const changes = seedDemo({ name: "Changes asked", status: "planning", confirmed_at: null, safety_approved_at: null });
    db.safetyReviews.push({
      id: "review-changes", event_id: changes.id, outcome: "changes_requested", checklist: {}, comments: "Move the stage.",
      internal_notes: null, areas: ["layout"], reviewer: { id: "officer", name: "Sam Koh" }, created_at: "2026-10-02T01:00:00Z",
    });
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));

    for (const name of ["Still approved", "Changes asked"]) {
      await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
      await screen.findByRole("region", { name: "Safety review" });
      expect(screen.queryByText("A new safety review is needed.")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Back to review queue" }));
    }
  });

  it("TC-US29B-31: the Safety officer is told an event with open flags can't be reviewed yet (D106)", async () => {
    const user = userEvent.setup();
    const event = seedRequest({ name: "Alumni night", status: "approved", coordinator: CASEY });
    seedBooking(event, seedVenue({ name: "SCIS Seminar Room 2-1" }), { status: "approved", expected_attendees: 40 });
    server.use(
      http.post("*/api/v1/safety-reviews/:id", () =>
        HttpResponse.json({ code: "SAFETY_REVIEW_NOT_ALLOWED", reason: "review_flags_open", status: "approved" }, { status: 409 }),
      ),
    );
    setDevRole("safety_officer");
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Safety reviews" }));
    await user.click(await screen.findByRole("button", { name: /Alumni night/ }));
    await screen.findByRole("heading", { name: "Safety review" });
    for (const group of screen.getAllByRole("group").filter((g) => within(g).queryAllByRole("radio").length > 0)) {
      await user.click(within(group).getByRole("radio", { name: "Satisfactory" }));
    }
    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This event has arrangements to review after an approved change. It returns to the queue once its coordinator has reviewed them.",
    );
  });
});

describe("the organiser sees each decision (US29b AC 4)", () => {
  it("TC-US29B-32: shows Approved or Rejected, the decision date and why it was rejected", async () => {
    setDevRole("organiser");
    const user = userEvent.setup();
    const event = seedDemo();
    moveLater(event, { status: "approved", decided_at: "2026-10-02T02:00:00Z" });
    seedChangeRequest(event, {
      reason: "A bigger room.",
      changes: [{ field: "expected_attendees", old_value: 20, new_value: 60 }],
      status: "rejected",
      decided_at: "2026-10-03T02:00:00Z",
      rejection_reason: "No larger room is free that day.",
    });
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
    await user.click(await screen.findByRole("button", { name: /Change Request Demo/ }));

    const list = within(await screen.findByRole("list", { name: "Your change requests" }));
    const [rejected, approved] = list.getAllByRole("listitem");
    expect(approved).toHaveTextContent("Approved");
    expect(approved).toHaveTextContent("Decided Fri, Oct 2, 10:00 AM");
    expect(rejected).toHaveTextContent("Rejected");
    expect(rejected).toHaveTextContent("Decided Sat, Oct 3, 10:00 AM");
    expect(rejected).toHaveTextContent("Why it was rejected: No larger room is free that day.");
  });
});
