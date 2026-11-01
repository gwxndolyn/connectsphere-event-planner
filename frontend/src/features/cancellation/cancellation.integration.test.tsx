import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { COORDINATOR_ID, callsTo, db, seedRequest, server, startMockBackend } from "../../test/server";

// US9 (SCRUM-12): the real App, the organiser's request and the coordinator's review screen against the fake
// backend. Which events can be cancelled, the start rule, what's released and who's told are the API's
// (backend/tests/event/test_cancellations.py); these check what the screens offer, send and show.
startMockBackend();

const CASEY = { id: COORDINATOR_ID, name: "Casey Tan" };

type User = ReturnType<typeof userEvent.setup>;

async function open(user: User, role: "organiser" | "coordinator", name: string) {
  setDevRole(role);
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
}

async function panel() {
  return within(await screen.findByRole("region", { name: "Cancellation" }));
}

function plannedEvent(overrides: Parameters<typeof seedRequest>[0] = {}) {
  return seedRequest({
    name: "Alumni night",
    status: "planning",
    coordinator: CASEY,
    request_reference: "ER-2026-000321",
    ...overrides,
  });
}

describe("cancel an event (US9)", () => {
  it("TC-US9-26: the organiser asks to cancel with a reason, and then waits for the coordinator (AC 1)", async () => {
    const user = userEvent.setup();
    const event = plannedEvent({ status: "approved" });
    await open(user, "organiser", "Alumni night");
    const cancellation = await panel();

    await user.click(await cancellation.findByRole("button", { name: "Request cancellation" }));
    await user.click(cancellation.getByRole("button", { name: "Send cancellation request" }));
    expect(cancellation.getByRole("alert")).toHaveTextContent("Give a reason");
    expect(cancellation.getByLabelText("Reason for cancelling")).toHaveAttribute("aria-invalid", "true");
    expect(callsTo("POST", /cancellation-requests$/)).toHaveLength(0);

    await user.type(cancellation.getByLabelText("Reason for cancelling"), "The keynote speaker can't travel.");
    await user.click(cancellation.getByRole("button", { name: "Send cancellation request" }));

    expect(await cancellation.findByRole("status")).toHaveTextContent("Cancellation request sent.");
    expect(callsTo("POST", `/api/v1/event-requests/${event.id}/cancellation-requests`)[0].body).toEqual({
      reason: "The keynote speaker can't travel.",
    });
    const history = cancellation.getByRole("list", { name: "Cancellation history" });
    expect(history).toHaveTextContent("Requested by Olivia Organiser");
    expect(history).toHaveTextContent("Reason: The keynote speaker can't travel.");
    expect(history).toHaveTextContent("Waiting for decision");
    expect(cancellation.getByText(/waiting for your coordinator's decision/)).toBeInTheDocument();
    expect(cancellation.queryByRole("button", { name: "Request cancellation" })).not.toBeInTheDocument();
  });

  it("TC-US9-27: nothing to cancel before approval, and no new request once cancelled (AC 1, 4)", async () => {
    const user = userEvent.setup();
    seedRequest({ name: "Under review", status: "under_review", coordinator: CASEY });
    plannedEvent({ name: "Called off", status: "cancelled" });

    await open(user, "organiser", "Under review");
    expect(screen.queryByRole("region", { name: "Cancellation" })).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Back to my requests" })[0]);
    await user.click(await screen.findByRole("button", { name: /Called off/ }));
    const cancellation = await panel();
    expect(cancellation.getByText("This event is cancelled.")).toBeInTheDocument();
    expect(cancellation.queryByRole("button", { name: "Request cancellation" })).not.toBeInTheDocument();
  });

  it("TC-US9-28: the coordinator approves the organiser's request, and the event shows Cancelled (AC 2, 4, 8)", async () => {
    const user = userEvent.setup();
    const event = plannedEvent();
    db.cancellations.push({
      id: "cancellation-1",
      event_id: event.id,
      event_name: event.name,
      request_reference: event.request_reference,
      event_status: "planning",
      status: "pending",
      reason: "The keynote speaker can't travel.",
      requested_by: { id: "organiser-id", name: "Olivia Organiser" },
      requested_at: "2026-10-01T02:00:00Z",
      decided_by: null,
      decided_at: null,
      rejection_reason: null,
      direct: false,
    });
    await open(user, "coordinator", "Alumni night");
    const cancellation = await panel();

    expect(await cancellation.findByText(/asked to cancel this event: The keynote speaker can't travel./)).toBeInTheDocument();
    expect(cancellation.queryByRole("button", { name: "Cancel event" })).not.toBeInTheDocument();
    await user.click(cancellation.getByRole("button", { name: "Approve cancellation" }));

    expect(await cancellation.findByRole("status")).toHaveTextContent("The event is cancelled.");
    expect(cancellation.getByText("This event is cancelled.")).toBeInTheDocument();
    const history = cancellation.getByRole("list", { name: "Cancellation history" });
    expect(history).toHaveTextContent("Approved by Casey Tan on");
    expect(history).toHaveTextContent("Cancelled");
    expect(callsTo("POST", "/api/v1/event-cancellations/cancellation-1/approve")).toHaveLength(1);
    expect(db.requests[0].status).toBe("cancelled");
  });

  it("TC-US9-29: rejecting needs a reason, which the record then shows (AC 2, 8)", async () => {
    const user = userEvent.setup();
    const event = plannedEvent();
    db.cancellations.push({
      id: "cancellation-1",
      event_id: event.id,
      event_name: event.name,
      request_reference: event.request_reference,
      event_status: "planning",
      status: "pending",
      reason: "Low sign-ups.",
      requested_by: { id: "organiser-id", name: "Olivia Organiser" },
      requested_at: "2026-10-01T02:00:00Z",
      decided_by: null,
      decided_at: null,
      rejection_reason: null,
      direct: false,
    });
    await open(user, "coordinator", "Alumni night");
    const cancellation = await panel();

    await user.click(await cancellation.findByRole("button", { name: "Reject cancellation" }));
    await user.click(cancellation.getByRole("button", { name: "Reject cancellation" }));
    expect(cancellation.getByRole("alert")).toHaveTextContent("Give a reason");
    expect(callsTo("POST", /\/reject$/)).toHaveLength(0);

    await user.type(cancellation.getByLabelText("Reason for rejecting"), "Registrations are strong.");
    await user.click(cancellation.getByRole("button", { name: "Reject cancellation" }));

    expect(await cancellation.findByRole("status")).toHaveTextContent("Cancellation request rejected.");
    expect(callsTo("POST", "/api/v1/event-cancellations/cancellation-1/reject")[0].body).toEqual({
      reason: "Registrations are strong.",
    });
    const history = cancellation.getByRole("list", { name: "Cancellation history" });
    expect(history).toHaveTextContent("Rejected by Casey Tan on");
    expect(history).toHaveTextContent("Why it was rejected: Registrations are strong.");
    expect(db.requests[0].status).toBe("planning");
    expect(cancellation.getByRole("button", { name: "Cancel event" })).toBeInTheDocument();
  });

  it("TC-US9-30: the coordinator cancels directly only after confirming it can't be undone (AC 3, 4)", async () => {
    const user = userEvent.setup();
    const event = plannedEvent();
    await open(user, "coordinator", "Alumni night");
    const cancellation = await panel();

    await user.click(await cancellation.findByRole("button", { name: "Cancel event" }));
    await user.type(cancellation.getByLabelText("Reason for cancelling"), "The venue flooded.");
    await user.click(cancellation.getByRole("button", { name: "Continue" }));

    const confirm = within(cancellation.getByRole("group", { name: "Confirm cancellation" }));
    expect(confirm.getByRole("heading", { name: "Cancel Alumni night?" })).toBeInTheDocument();
    expect(confirm.getByText(/This can't be undone./)).toBeInTheDocument();
    expect(confirm.getByText(/The venue flooded./)).toBeInTheDocument();
    expect(callsTo("POST", /\/cancellation$/)).toHaveLength(0);

    await user.click(confirm.getByRole("button", { name: "Cancel event" }));

    expect(await cancellation.findByRole("status")).toHaveTextContent("The event is cancelled.");
    expect(callsTo("POST", `/api/v1/event-requests/${event.id}/cancellation`)[0].body).toEqual({ reason: "The venue flooded." });
    expect(cancellation.getByRole("list", { name: "Cancellation history" })).toHaveTextContent("Cancelled by Casey Tan on");
    expect(cancellation.queryByRole("button", { name: "Cancel event" })).not.toBeInTheDocument();
  });

  it("TC-US9-31: the API's refusal is explained and nothing changes (AC 7)", async () => {
    const user = userEvent.setup();
    const event = plannedEvent();
    server.use(
      http.post(`http://api.test/api/v1/event-requests/${event.id}/cancellation`, () =>
        HttpResponse.json({ code: "EVENT_STARTED", starts_at: "2026-10-01T01:00:00Z" }, { status: 409 }),
      ),
    );
    await open(user, "coordinator", "Alumni night");
    const cancellation = await panel();

    await user.click(await cancellation.findByRole("button", { name: "Cancel event" }));
    await user.type(cancellation.getByLabelText("Reason for cancelling"), "Too late.");
    await user.click(cancellation.getByRole("button", { name: "Continue" }));
    await user.click(cancellation.getByRole("button", { name: "Cancel event" }));

    expect(await cancellation.findByRole("alert")).toHaveTextContent("This event has already started, so it can't be cancelled.");
    expect(db.requests[0].status).toBe("planning");
  });

  it("TC-US9-31: if the history can't be loaded, nothing is offered, since a request may already be waiting", async () => {
    const user = userEvent.setup();
    const event = plannedEvent();
    server.use(
      http.get(`http://api.test/api/v1/event-requests/${event.id}/cancellations`, () =>
        HttpResponse.json({ code: "INTERNAL" }, { status: 500 }),
      ),
    );
    await open(user, "coordinator", "Alumni night");
    const cancellation = await panel();

    expect(await cancellation.findByRole("alert")).toHaveTextContent("Check the backend connection");
    expect(cancellation.queryByRole("button", { name: "Cancel event" })).not.toBeInTheDocument();
    expect(cancellation.queryByText("No cancellation requests for this event.")).not.toBeInTheDocument();
  });
});
