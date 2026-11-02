import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import {
  COORDINATOR_ID,
  callsTo,
  db,
  seedBooking,
  seedChangeRequest,
  seedRequest,
  seedVenue,
  startMockBackend,
} from "../../test/server";

// US29b (SCRUM-144, D102): a Coordinator Lead decides a coordinator's own US12 critical edit, which the coordinator
// can't decide themselves (D51). The same review panel as the coordinator's (SCRUM-143); the API's rule is proven by
// backend/tests/event/test_change_request_decisions.py, so here what the Lead's screen lists, sends and refuses.
startMockBackend();

const CASEY = { id: COORDINATOR_ID, name: "Casey Tan" };

// Capacity is an event's (US12), not on the request type the fake stores; read and set it as the API does.
const capacityOf = (id: string) => (db.requests.find((r) => r.id === id) as { capacity?: number } | undefined)?.capacity;

beforeEach(() => setDevRole("coordinator_lead"));

type User = ReturnType<typeof userEvent.setup>;

/** A planning event assigned to Casey with an approved booking, and Casey's held capacity edit on it. */
function seedHeldEdit() {
  const event = seedRequest({ name: "Data Science Workshop", status: "planning", coordinator: CASEY, expected_attendees: 60 });
  Object.assign(event, { capacity: 60 });
  seedBooking(event, seedVenue({ name: "SCIS Seminar Room 2-1" }), { status: "approved", expected_attendees: 60 });
  const edit = seedChangeRequest(event, {
    requested_by_user_id: COORDINATOR_ID,
    reason: "A bigger room is free that day.",
    changes: [{ field: "capacity", old_value: 60, new_value: 80 }],
  });
  return { event, edit };
}

async function openLeadQueue(user: User) {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  await screen.findByRole("heading", { name: "Unassigned requests" });
}

async function reviewEdit(user: User) {
  await openLeadQueue(user);
  const section = await screen.findByRole("region", { name: /Coordinator edits to approve/ });
  const row = within(section).getByRole("listitem", { name: /Data Science Workshop/ });
  await user.click(within(row).getByRole("button", { name: "Review" }));
  const panel = await screen.findByRole("region", { name: "Change requests for this event" });
  await within(panel).findAllByRole("article");
  return panel;
}

describe("the Lead decides a coordinator's own edit (US29b, SCRUM-144)", () => {
  it("TC-US29B-37: lists Casey's held capacity edit, opens it, approves it, and the event takes the value (D102)", async () => {
    const user = userEvent.setup();
    const { event, edit } = seedHeldEdit();
    await openLeadQueue(user);

    const section = await screen.findByRole("region", { name: /Coordinator edits to approve/ });
    expect(within(section).getByRole("heading", { name: "Coordinator edits to approve (1)" })).toBeInTheDocument();
    const row = within(section).getByRole("listitem", { name: /Data Science Workshop/ });
    expect(row).toHaveTextContent("Casey Tan");
    expect(row).toHaveTextContent("Requested");
    expect(row).toHaveTextContent("Significant");

    await user.click(within(row).getByRole("button", { name: "Review" }));
    const panel = await screen.findByRole("region", { name: "Change requests for this event" });
    const request = await within(panel).findByRole("article");
    expect(request).toHaveTextContent("Casey Tan asked");
    expect(request).toHaveTextContent("(a critical edit)");
    const capacity = within(request).getByRole("row", { name: /Capacity/ });
    expect(capacity).toHaveTextContent("60");
    expect(capacity).toHaveTextContent("80");
    expect(request).toHaveTextContent("A bigger room is free that day.");
    expect(within(request).getByRole("note", { name: "What approving does" })).toHaveTextContent("flags 1 venue booking");

    await user.click(within(request).getByRole("button", { name: "Approve" }));
    expect(callsTo("POST", `/api/v1/change-requests/${edit.id}/approve`)).toHaveLength(0);
    await user.click(within(request).getByRole("button", { name: "Approve change" }));

    expect(await within(panel).findByRole("status")).toHaveTextContent("Approved. The event is now Planning.");
    expect(capacityOf(event.id)).toBe(80);
    expect(db.changeRequests.find((r) => r.id === edit.id)?.decided_by?.name).toBe("Lena Lead");
    // Back on the queue, the list has reloaded and nothing waits.
    await user.click(screen.getByRole("button", { name: "Back to queue" }));
    await screen.findByRole("heading", { name: "Unassigned requests" });
    expect(screen.queryByRole("region", { name: /Coordinator edits to approve/ })).not.toBeInTheDocument();
  });

  it("TC-US29B-37: the coordinator then sees the flag the Lead's approval raised", async () => {
    const user = userEvent.setup();
    seedHeldEdit();
    const panel = await reviewEdit(user);
    await user.click(within(panel).getByRole("button", { name: "Approve" }));
    await user.click(within(panel).getByRole("button", { name: "Approve change" }));
    await within(panel).findByRole("status");
    document.body.innerHTML = "";

    setDevRole("coordinator");
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
    // Casey's own edit was never in Casey's list.
    expect(screen.queryByRole("region", { name: /Change requests to review/ })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /Data Science Workshop/ }));
    const flags = await screen.findByRole("region", { name: "Review after change" });
    const item = within(flags).getByRole("listitem");
    expect(item).toHaveTextContent("SCIS Seminar Room 2-1");
    expect(item).toHaveTextContent("Capacity");
    expect(within(item).getByRole("button", { name: "Mark reviewed" })).toBeInTheDocument();
  });

  it("TC-US29B-38: rejecting needs a reason first, then the edit leaves the list (D102)", async () => {
    const user = userEvent.setup();
    const { event, edit } = seedHeldEdit();
    const panel = await reviewEdit(user);
    const request = within(panel).getByRole("article");

    await user.click(within(request).getByRole("button", { name: "Reject" }));
    await user.click(within(request).getByRole("button", { name: "Reject change" }));
    expect(within(request).getByText("Give a reason for rejecting.")).toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/change-requests/${edit.id}/reject`)).toHaveLength(0);

    await user.type(within(request).getByLabelText("Reason for rejecting"), "The bigger room has no projector.");
    await user.click(within(request).getByRole("button", { name: "Reject change" }));

    expect(await within(panel).findByRole("status")).toHaveTextContent("Rejected. The event keeps its current details.");
    expect(callsTo("POST", `/api/v1/change-requests/${edit.id}/reject`)).toHaveLength(1);
    expect(db.changeRequests.find((r) => r.id === edit.id)?.rejection_reason).toBe("The bigger room has no projector.");
    expect(capacityOf(event.id)).toBe(60);
    await user.click(screen.getByRole("button", { name: "Back to queue" }));
    await screen.findByRole("heading", { name: "Unassigned requests" });
    expect(screen.queryByRole("region", { name: /Coordinator edits to approve/ })).not.toBeInTheDocument();
  });

  it("TC-US29B-38: the Lead doesn't see an organiser's request, and the section hides when none waits", async () => {
    const user = userEvent.setup();
    const event = seedRequest({ name: "Data Science Workshop", status: "planning", coordinator: CASEY });
    seedChangeRequest(event, { reason: "A clearer title.", changes: [{ field: "name", old_value: event.name, new_value: "Data Science Day" }] });
    await openLeadQueue(user);

    expect(await screen.findByRole("tab", { name: /Unassigned/ })).toBeInTheDocument();
    expect(callsTo("GET", /^\/api\/v1\/change-requests/).length).toBeGreaterThan(0);
    // The Lead's list is asked for as the Lead (acting_as, #127).
    expect(callsTo("GET", /^\/api\/v1\/change-requests/).every((call) => call.url.searchParams.get("acting_as") === "coordinator_lead")).toBe(true);
    expect(screen.queryByRole("region", { name: /Coordinator edits to approve/ })).not.toBeInTheDocument();
    expect(screen.queryByText("A clearer title.")).not.toBeInTheDocument();
  });

  it("TC-US29B-39: opens an edit on a Planning event the Lead can't read, from the change request alone, and approves it", async () => {
    const user = userEvent.setup();
    const { event, edit } = seedHeldEdit();

    const panel = await reviewEdit(user);

    // The event itself is the coordinator's past the request stage (_can_read): the screen never asks for it.
    expect(callsTo("GET", `/api/v1/event-requests/${event.id}`)).toHaveLength(0);
    const loads = callsTo("GET", `/api/v1/change-requests/${edit.id}`);
    expect(loads.length).toBeGreaterThan(0);
    expect(loads.every((call) => call.url.searchParams.get("acting_as") === "coordinator_lead")).toBe(true);
    expect(screen.queryByText("This request is no longer available.")).not.toBeInTheDocument();
    expect(panel).toHaveTextContent("Data Science Workshop");
    const rows = within(within(panel).getByRole("table", { name: "Requested changes" })).getAllByRole("row").slice(1);
    expect(rows.map((row) => within(row).getAllByRole("cell").map((cell) => cell.textContent))).toEqual([["Capacity", "60", "80"]]);

    await user.click(within(panel).getByRole("button", { name: "Approve" }));
    await user.click(within(panel).getByRole("button", { name: "Approve change" }));
    expect(await within(panel).findByRole("status")).toHaveTextContent("Approved. The event is now Planning.");
    expect(capacityOf(event.id)).toBe(80);
    expect(within(panel).queryByRole("article")).not.toBeInTheDocument();
  });
});
