import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { COORDINATOR_PERSON, LEAD_PERSON, callsTo, db, seedRequest, server, startMockBackend } from "../../test/server";

// SCRUM-13 (US10a): the Lead's queue and assign screens, and what the organiser sees afterwards.
startMockBackend();

beforeEach(() => setDevRole("organiser"));

async function openEventRequestsAs(user: ReturnType<typeof userEvent.setup>, role: "organiser" | "coordinator" | "coordinator_lead") {
  render(<App />);
  await user.selectOptions(screen.getByLabelText("Acting as"), role);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
}

describe("Coordinator Lead: assign a coordinator (US10a)", () => {
  it("TC-US10A-21: lists unassigned requests with what the Lead needs, assigns one and it leaves the queue", async () => {
    seedRequest({ status: "submitted", name: "Alumni night", expected_attendees: 120, preferred_dates: ["2026-11-20", "2026-11-27"] });
    seedRequest({ status: "draft", name: "A private draft" });
    seedRequest({ status: "under_review", name: "Already reviewed", coordinator: { id: "c1", name: "Someone" } });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");

    expect(await screen.findByRole("heading", { name: "Unassigned requests" })).toBeInTheDocument();
    const queue = screen.getByRole("tabpanel", { name: "Unassigned" });
    // AC 2: name, organiser, preferred dates, expected attendance and status.
    expect(within(queue).getByText("Alumni night")).toBeInTheDocument();
    expect(queue).toHaveTextContent("Organiser: Olivia Organiser");
    expect(queue).toHaveTextContent("Preferred dates: 2026-11-20, 2026-11-27");
    expect(queue).toHaveTextContent("Expected attendance: 120");
    expect(queue).toHaveTextContent("submitted");
    // AC 1, 5: drafts and requests that already have a coordinator aren't queued.
    expect(screen.queryByText("A private draft")).not.toBeInTheDocument();
    expect(within(queue).queryByText("Already reviewed")).not.toBeInTheDocument();
    expect(callsTo("GET", "/api/v1/event-requests/unassigned")[0].headers.get("X-User-Id")).toBe("lead-id");

    await user.click(screen.getByRole("button", { name: "Assign Alumni night" }));
    expect(await screen.findByRole("heading", { name: "Assign a coordinator" })).toBeInTheDocument();
    // Nothing is chosen yet, so nothing can be confirmed.
    expect(screen.getByRole("button", { name: "Confirm assignment" })).toBeDisabled();

    await user.click(screen.getByLabelText(/Casey Tan/));
    await user.click(screen.getByRole("button", { name: "Confirm assignment" }));

    expect(await screen.findByRole("heading", { name: "Coordinator assigned" })).toBeInTheDocument();
    expect(screen.getByText("Casey Tan", { selector: "strong" })).toBeInTheDocument();
    expect(callsTo("POST", /\/assignment$/)[0].body).toEqual({ coordinator_id: COORDINATOR_PERSON.id });
    expect(db.requests.find((r) => r.name === "Alumni night")).toMatchObject({ status: "under_review" });

    await user.click(screen.getByRole("button", { name: "Back to queue" }));
    expect(await screen.findByText("No requests are waiting for a coordinator.")).toBeInTheDocument();
  });

  it("TC-US10A-22: says why when the backend refuses the pick, and keeps the request queued", async () => {
    seedRequest({ status: "submitted", name: "Alumni night" });
    server.use(
      http.post("http://api.test/api/v1/event-requests/:id/assignment", () =>
        HttpResponse.json({ code: "INVALID_COORDINATOR", reason: "inactive" }, { status: 422 }),
      ),
    );
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");
    await user.click(await screen.findByRole("button", { name: "Assign Alumni night" }));
    await user.click(await screen.findByLabelText(/Casey Tan/));
    await user.click(screen.getByRole("button", { name: "Confirm assignment" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("That coordinator is inactive.");
    expect(screen.getByRole("heading", { name: "Assign a coordinator" })).toBeInTheDocument();
    expect(db.requests[0]).toMatchObject({ status: "submitted", coordinator: null });
  });

  it("TC-US10A-23: drops a request from the queue when someone else assigned it first", async () => {
    seedRequest({ status: "submitted", name: "Alumni night" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");
    await user.click(await screen.findByRole("button", { name: "Assign Alumni night" }));
    await user.click(await screen.findByLabelText(/Casey Tan/));
    // Another Lead gets there first.
    Object.assign(db.requests[0], { status: "under_review", coordinator: { id: "x", name: "Taken" } });
    await user.click(screen.getByRole("button", { name: "Confirm assignment" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("no longer waiting for a coordinator");
    await user.click(screen.getByRole("button", { name: "Back to queue" }));
    expect(await screen.findByText("No requests are waiting for a coordinator.")).toBeInTheDocument();
  });

  it("TC-US10A-24: shows no Assign action to an organiser or a coordinator (AC 6)", async () => {
    seedRequest({ status: "submitted", name: "Alumni night" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator");
    expect(await screen.findByRole("heading", { name: "Requests to review" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Assign/ })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Acting as"), "organiser");
    expect(await screen.findByRole("heading", { name: "My event requests" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Assign/ })).not.toBeInTheDocument();
  });
});

describe("Coordinator Lead: sees workload in the picker (US10b)", () => {
  it("TC-US10B-07: shows each coordinator's name and how many events they are planning, 0 when none", async () => {
    seedRequest({ status: "submitted", name: "Alumni night" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");
    await user.click(await screen.findByRole("button", { name: "Assign Alumni night" }));

    const option = (await screen.findByLabelText(/Casey Tan/)).closest("label")!;
    expect(option).toHaveTextContent("Casey Tan");
    expect(option).toHaveTextContent("0 events planning");
  });

  it("TC-US10B-08: counts only events being worked, and is one higher after assigning", async () => {
    const casey = { id: "coordinator-id", name: "Casey Tan" };
    seedRequest({ status: "under_review", name: "Careers fair", coordinator: casey });
    seedRequest({ status: "planning", name: "Open day", coordinator: casey });
    // Not being worked: rejected and cancelled events don't count.
    seedRequest({ status: "rejected", name: "Old idea", coordinator: casey });
    seedRequest({ status: "cancelled", name: "Called off", coordinator: casey });
    seedRequest({ status: "submitted", name: "Alumni night" });
    seedRequest({ status: "submitted", name: "Hack night" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");

    await user.click(await screen.findByRole("button", { name: "Assign Alumni night" }));
    expect((await screen.findByLabelText(/Casey Tan/)).closest("label")).toHaveTextContent("2 events planning");
    await user.click(screen.getByLabelText(/Casey Tan/));
    await user.click(screen.getByRole("button", { name: "Confirm assignment" }));
    expect(await screen.findByRole("heading", { level: 2, name: "Coordinator assigned" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to queue" }));

    // AC 3: the next time the picker opens, their count is one higher.
    await user.click(await screen.findByRole("button", { name: "Assign Hack night" }));
    expect((await screen.findByLabelText(/Casey Tan/)).closest("label")).toHaveTextContent("3 events planning");
  });

  it("TC-US10B-09: says '1 event planning' in the singular", async () => {
    seedRequest({ status: "under_review", name: "Careers fair", coordinator: { id: "coordinator-id", name: "Casey Tan" } });
    seedRequest({ status: "submitted", name: "Alumni night" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");
    await user.click(await screen.findByRole("button", { name: "Assign Alumni night" }));

    expect((await screen.findByLabelText(/Casey Tan/)).closest("label")).toHaveTextContent("1 event planning");
  });
});

describe("organiser: sees the coordinator (US10a AC 8)", () => {
  it("TC-US10A-25: shows Unassigned before assignment and the coordinator's name after", async () => {
    seedRequest({ status: "submitted", name: "Alumni night" });
    seedRequest({ status: "under_review", name: "Careers fair", coordinator: { id: "c1", name: "Casey Tan" } });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "organiser");

    const careers = (await screen.findByText("Careers fair")).closest("button")!;
    const alumni = screen.getByText("Alumni night").closest("button")!;
    expect(alumni).toHaveTextContent("Coordinator: Unassigned");
    expect(careers).toHaveTextContent("Coordinator: Casey Tan");
  });
});

// A request `by` assigned to `to` (the history record that puts it in that Lead's scope).
function seedAssigned(
  overrides: Parameters<typeof seedRequest>[0],
  to: { id: string; name: string; email: string } = COORDINATOR_PERSON,
  by: { id: string; name: string; email: string } = LEAD_PERSON,
) {
  const request = seedRequest({ status: "under_review", coordinator: { id: to.id, name: to.name }, ...overrides });
  db.assignments[request.id] = [
    { id: `a-${request.id}`, kind: "assignment", assigned_by: by, coordinator: to, created_at: "2026-10-20T01:00:00Z" },
  ];
  return request;
}

const DANA = { id: "dana-id", name: "Dana Lim", email: "dana@smu.edu.sg" };
const OTHER_LEAD = { id: "other-lead-id", name: "Leo Lee", email: "leo.lee@smu.edu.sg" };

async function openAssignedTab(user: ReturnType<typeof userEvent.setup>) {
  await openEventRequestsAs(user, "coordinator_lead");
  await user.click(await screen.findByRole("tab", { name: "Assigned" }));
  return screen.findByRole("tabpanel", { name: "Assigned" });
}

describe("Coordinator Lead: views the assignment history (US10d)", () => {
  it("TC-US10D-11: shows the entry made by assigning: kind, Lead, coordinator and time", async () => {
    seedRequest({ status: "submitted", name: "Alumni night" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");
    await user.click(await screen.findByRole("button", { name: "Assign Alumni night" }));
    await user.click(await screen.findByLabelText(/Casey Tan/));
    await user.click(screen.getByRole("button", { name: "Confirm assignment" }));

    await user.click(await screen.findByRole("button", { name: "View assignment history" }));

    expect(await screen.findByRole("heading", { name: "Assignment history" })).toBeInTheDocument();
    const [entry] = within(screen.getByRole("region", { name: "Assignment history" })).getAllByRole("listitem");
    expect(entry).toHaveTextContent("Assignment");
    expect(entry).toHaveTextContent("Lena Lead assigned Casey Tan");
    expect(entry).toHaveTextContent("24 Oct 2026");
    expect(callsTo("GET", /\/assignment-history$/)[0].headers.get("X-User-Id")).toBe("lead-id");
  });

  it("TC-US10D-12: opens the history of an assigned request, newest first, marking a reassignment", async () => {
    const request = seedAssigned({ name: "Careers fair" }, DANA);
    const earlier = { id: "a1", kind: "assignment" as const, assigned_by: LEAD_PERSON, coordinator: COORDINATOR_PERSON, created_at: "2026-10-20T01:00:00Z" };
    db.assignments[request.id] = [
      { ...earlier, id: "a2", kind: "reassignment", coordinator: DANA, created_at: "2026-10-22T09:30:00Z" },
      earlier,
    ];
    const user = userEvent.setup();
    const assigned = await openAssignedTab(user);
    expect(assigned).toHaveTextContent("Careers fair");
    expect(assigned).toHaveTextContent("Coordinator: Dana Lim");
    await user.click(within(assigned).getByRole("button", { name: "Assignment history for Careers fair" }));

    const entries = within(await screen.findByRole("region", { name: "Assignment history" })).getAllByRole("listitem");
    expect(entries).toHaveLength(2);
    expect(entries[0]).toHaveTextContent("Reassignment");
    expect(entries[0]).toHaveTextContent("Lena Lead assigned Dana Lim");
    expect(entries[1]).toHaveTextContent("Casey Tan");
    expect(entries[1]).not.toHaveTextContent("Reassignment");
  });

  it("TC-US10D-13: says so when an assigned request has no records", async () => {
    seedAssigned({ name: "Careers fair" });
    server.use(
      http.get("http://api.test/api/v1/event-requests/:id/assignment-history", () => HttpResponse.json({ assignments: [] })),
    );
    const user = userEvent.setup();
    await openAssignedTab(user);
    await user.click(await screen.findByRole("button", { name: "Assignment history for Careers fair" }));

    expect(await screen.findByText("No assignments have been recorded for this event.")).toBeInTheDocument();
  });

  it("TC-US10D-14: shows no history to a coordinator or an organiser", async () => {
    seedRequest({ status: "under_review", name: "Careers fair", coordinator: { id: "c1", name: "Casey Tan" } });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator");
    expect(await screen.findByRole("heading", { name: "Requests to review" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Assignment history/ })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Acting as"), "organiser");
    expect(await screen.findByRole("heading", { name: "My event requests" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Assignment history/ })).not.toBeInTheDocument();
  });
});

describe("Coordinator Lead: queue and oversight view (US19)", () => {
  it("TC-US19-12: has an Unassigned tab (shown first) and an Assigned tab", async () => {
    seedRequest({ status: "submitted", name: "Alumni night" });
    seedAssigned({ name: "Careers fair" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");

    expect(await screen.findByRole("tab", { name: "Unassigned", selected: true })).toBeInTheDocument();
    expect(screen.getByRole("tabpanel", { name: "Unassigned" })).toHaveTextContent("Alumni night");
    expect(screen.queryByText("Careers fair")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Assigned" }));
    const assigned = await screen.findByRole("tabpanel", { name: "Assigned" });
    expect(assigned).toHaveTextContent("Careers fair");
    expect(screen.queryByText("Alumni night")).not.toBeInTheDocument();
  });

  it("TC-US19-13: the Assigned tab shows coordinator, status and event date for each event (AC 2)", async () => {
    seedAssigned({ name: "Careers fair", status: "approved", preferred_dates: ["2026-12-03"] });
    const user = userEvent.setup();
    const assigned = await openAssignedTab(user);

    expect(assigned).toHaveTextContent("Careers fair");
    expect(assigned).toHaveTextContent("Coordinator: Casey Tan");
    expect(assigned).toHaveTextContent("approved");
    expect(assigned).toHaveTextContent("Event date: 2026-12-03");
    expect(callsTo("GET", /\/assigned$/)[0].headers.get("X-User-Id")).toBe("lead-id");
  });

  it("TC-US19-14: shows only events this Lead assigned, so a second Lead sees their own (AC 6)", async () => {
    seedAssigned({ name: "Mine" });
    seedAssigned({ name: "Theirs" }, COORDINATOR_PERSON, OTHER_LEAD);
    const user = userEvent.setup();
    const assigned = await openAssignedTab(user);

    expect(assigned).toHaveTextContent("Mine");
    expect(assigned).not.toHaveTextContent("Theirs");
  });

  it("TC-US19-15: filters by coordinator and by status, and says when nothing matches (AC 3)", async () => {
    seedAssigned({ name: "A", status: "under_review" });
    seedAssigned({ name: "B", status: "approved" }, DANA);
    const user = userEvent.setup();
    const assigned = await openAssignedTab(user);
    expect(assigned).toHaveTextContent("A");
    expect(assigned).toHaveTextContent("B");

    await user.selectOptions(screen.getByLabelText("Coordinator"), "Dana Lim");
    await waitFor(() => expect(screen.getByRole("tabpanel", { name: "Assigned" })).not.toHaveTextContent("Coordinator: Casey Tan"));
    expect(screen.getByRole("tabpanel", { name: "Assigned" })).toHaveTextContent("B");
    expect(callsTo("GET", /\/assigned$/).some((call) => call.url.search === "?coordinator_id=dana-id")).toBe(true);
    // The coordinator list doesn't shrink to the one just chosen.
    expect(within(screen.getByLabelText("Coordinator")).getAllByRole("option")).toHaveLength(3);

    await user.selectOptions(screen.getByLabelText("Status"), "under review");
    expect(await screen.findByText("No assigned events match these filters.")).toBeInTheDocument();
    expect(
      callsTo("GET", /\/assigned$/).some((call) => call.url.search === "?coordinator_id=dana-id&status=under_review"),
    ).toBe(true);
  });

  it("TC-US19-16: opens any listed event read-only, with Assign only on an unassigned one (AC 4)", async () => {
    seedRequest({ status: "submitted", name: "Alumni night", purpose: "Meet alumni" });
    seedAssigned({ name: "Careers fair", purpose: "Meet employers" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");

    await user.click(await screen.findByRole("button", { name: "View Alumni night" }));
    const detail = await screen.findByRole("region", { name: "Request details" });
    expect(detail).toHaveTextContent("Meet alumni");
    expect(detail).toHaveTextContent("CoordinatorUnassigned");
    // Read-only: nothing here edits, approves, rejects or confirms.
    expect(within(detail).queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Approve|Reject|Confirm/ })).not.toBeInTheDocument();
    await user.click(within(detail).getByRole("button", { name: "Assign a coordinator" }));
    expect(await screen.findByRole("heading", { name: "Assign a coordinator" })).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Back to queue" })[0]);
    await user.click(await screen.findByRole("tab", { name: "Assigned" }));
    await user.click(await screen.findByRole("button", { name: "View Careers fair" }));
    const assignedDetail = await screen.findByRole("region", { name: "Request details" });
    expect(assignedDetail).toHaveTextContent("Meet employers");
    expect(assignedDetail).toHaveTextContent("CoordinatorCasey Tan");
    expect(within(assignedDetail).queryByRole("button", { name: "Assign a coordinator" })).not.toBeInTheDocument();
    await user.click(within(assignedDetail).getByRole("button", { name: "Assignment history" }));
    expect(await screen.findByRole("heading", { name: "Assignment history" })).toBeInTheDocument();
  });

  it("TC-US19-17: an assignment made here appears on the Assigned tab", async () => {
    seedRequest({ status: "submitted", name: "Alumni night" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");
    await user.click(await screen.findByRole("button", { name: "Assign Alumni night" }));
    await user.click(await screen.findByLabelText(/Casey Tan/));
    await user.click(screen.getByRole("button", { name: "Confirm assignment" }));
    await user.click(await screen.findByRole("button", { name: "Back to queue" }));

    await user.click(screen.getByRole("tab", { name: "Assigned" }));
    expect(await screen.findByRole("tabpanel", { name: "Assigned" })).toHaveTextContent("Alumni night");
  });

  it("TC-US19-18: other roles get no Lead tabs and the backend refuses them (AC 5)", async () => {
    seedAssigned({ name: "Careers fair" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator");
    expect(await screen.findByRole("heading", { name: "Requests to review" })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Acting as"), "organiser");
    expect(await screen.findByRole("heading", { name: "My event requests" })).toBeInTheDocument();
    expect(screen.queryByRole("tab")).not.toBeInTheDocument();

    const refused = await fetch("http://api.test/api/v1/event-requests/assigned", { headers: { "X-User-Id": "organiser-id" } });
    expect(refused.status).toBe(403);
  });
});

describe("Coordinator Lead: reassign an event (US10e)", () => {
  async function openDetail(user: ReturnType<typeof userEvent.setup>, name: string) {
    await openEventRequestsAs(user, "coordinator_lead");
    await user.click(await screen.findByRole("tab", { name: "Assigned" }));
    await user.click(await screen.findByRole("button", { name: `View ${name}` }));
    return screen.findByRole("region", { name: "Request details" });
  }

  it("TC-US10E-25: moves the event to a different coordinator with a reason, and the history shows both", async () => {
    db.otherCoordinators.push(DANA);
    seedAssigned({ name: "Careers fair" });
    const user = userEvent.setup();
    const detail = await openDetail(user, "Careers fair");

    await user.click(within(detail).getByRole("button", { name: "Reassign to another coordinator" }));
    expect(await screen.findByRole("heading", { name: "Reassign an event" })).toBeInTheDocument();
    // AC 5: the current coordinator isn't offered; nothing can be confirmed without a pick and a reason.
    expect(screen.queryByLabelText(/Casey Tan/)).not.toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Confirm reassignment" });
    expect(confirm).toBeDisabled();
    await user.click(screen.getByLabelText(/Dana Lim/));
    expect(confirm).toBeDisabled();
    await user.type(screen.getByLabelText("Reason for reassigning"), "Casey is on leave");
    await user.click(confirm);

    expect(await screen.findByRole("heading", { name: "Event reassigned" })).toBeInTheDocument();
    expect(screen.getByText("Dana Lim", { selector: "strong" })).toBeInTheDocument();
    expect(callsTo("POST", /\/reassignment$/)[0].body).toEqual({ coordinator_id: DANA.id, reason: "Casey is on leave" });
    expect(db.requests.find((r) => r.name === "Careers fair")?.coordinator?.id).toBe(DANA.id);

    await user.click(screen.getByRole("button", { name: "View assignment history" }));
    const entries = within(await screen.findByRole("region", { name: "Assignment history" })).getAllByRole("listitem");
    expect(entries[0]).toHaveTextContent("Reassignment");
    expect(entries[0]).toHaveTextContent("Dana Lim");
    expect(entries[0]).toHaveTextContent("Reason: Casey is on leave");
  });

  it("TC-US10E-26: offers Reassign only on an active event that has a coordinator (AC 1)", async () => {
    seedAssigned({ name: "Careers fair" });
    seedRequest({ status: "submitted", name: "Alumni night" });
    const user = userEvent.setup();
    await openEventRequestsAs(user, "coordinator_lead");

    await user.click(await screen.findByRole("button", { name: "View Alumni night" }));
    const unassigned = await screen.findByRole("region", { name: "Request details" });
    expect(within(unassigned).queryByRole("button", { name: /Reassign/ })).not.toBeInTheDocument();
  });

  it("TC-US10E-27: says why when the backend refuses, and changes nothing", async () => {
    db.otherCoordinators.push(DANA);
    seedAssigned({ name: "Careers fair" });
    server.use(
      http.post("http://api.test/api/v1/event-requests/:id/reassignment", () =>
        HttpResponse.json({ code: "REASSIGNMENT_NOT_ALLOWED", status: "completed" }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    const detail = await openDetail(user, "Careers fair");
    await user.click(within(detail).getByRole("button", { name: "Reassign to another coordinator" }));
    await user.click(await screen.findByLabelText(/Dana Lim/));
    await user.type(screen.getByLabelText("Reason for reassigning"), "Leave");
    await user.click(screen.getByRole("button", { name: "Confirm reassignment" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("can no longer be reassigned");
    expect(screen.getByRole("heading", { name: "Reassign an event" })).toBeInTheDocument();
    expect(db.requests.find((r) => r.name === "Careers fair")?.coordinator?.id).toBe(COORDINATOR_PERSON.id);
  });

  it("TC-US10E-28: says there is nobody else to pick when Casey is the only coordinator", async () => {
    seedAssigned({ name: "Careers fair" });
    const user = userEvent.setup();
    const detail = await openDetail(user, "Careers fair");
    await user.click(within(detail).getByRole("button", { name: "Reassign to another coordinator" }));

    expect(await screen.findByText("There are no other active coordinators to assign.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm reassignment" })).toBeDisabled();
  });
});
