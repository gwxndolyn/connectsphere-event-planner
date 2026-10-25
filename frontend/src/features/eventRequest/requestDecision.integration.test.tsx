import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { COORDINATOR_ID, callsTo, seedRequest, server, startMockBackend } from "../../test/server";

// US17 (SCRUM-84): the real App, review screen and organiser screen against the fake backend.
// Which requests may be decided (AC 1, 6; D48, D51) is the API's rule, proven by
// backend/tests/event/test_event_request_decisions.py; here, what the screens offer, send and show.
startMockBackend();

const CASEY = { id: COORDINATOR_ID, name: "Casey Tan" };

beforeEach(() => setDevRole("coordinator"));

type User = ReturnType<typeof userEvent.setup>;

async function openRequest(user: User, name: string) {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
  await screen.findByRole("heading", { name: "Review request" });
}

function decision() {
  return within(screen.getByRole("region", { name: "Decision" }));
}

describe("coordinator decides a request (US17)", () => {
  it("approves their assigned request under review (AC 1, 2, 5)", async () => {
    const request = seedRequest({ name: "Alumni night", status: "under_review", coordinator: CASEY });
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    await user.click(decision().getByRole("button", { name: "Approve request" }));

    expect(await screen.findByRole("status", { name: "Decision" })).toHaveTextContent(/Approved by Casey Tan on/);
    expect(screen.queryByRole("region", { name: "Decision" })).not.toBeInTheDocument();
    const [call] = callsTo("POST", `/api/v1/event-requests/${request.id}/approve`);
    expect(call.headers.get("X-User-Id")).toBe("coordinator-id");
  });

  it("asks for a reason before rejecting, then shows it (AC 3, 5)", async () => {
    const request = seedRequest({ name: "Alumni night", status: "under_review", coordinator: CASEY });
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    await user.click(decision().getByRole("button", { name: "Reject request" }));
    await user.click(decision().getByRole("button", { name: "Confirm rejection" }));
    expect(decision().getByRole("alert")).toHaveTextContent("Give the organiser a reason");
    expect(decision().getByLabelText("Reason for rejecting")).toHaveAttribute("aria-invalid", "true");
    expect(callsTo("POST", `/api/v1/event-requests/${request.id}/reject`)).toHaveLength(0);

    await user.type(decision().getByLabelText("Reason for rejecting"), "The date clashes with exams.");
    await user.click(decision().getByRole("button", { name: "Confirm rejection" }));

    const outcome = await screen.findByRole("status", { name: "Decision" });
    expect(outcome).toHaveTextContent(/Rejected by Casey Tan on/);
    expect(outcome).toHaveTextContent("Reason: The date clashes with exams.");
    expect(callsTo("POST", `/api/v1/event-requests/${request.id}/reject`)[0].body).toEqual({
      reason: "The date clashes with exams.",
    });
  });

  it("isn't offered on another coordinator's request or one awaiting clarification (AC 1)", async () => {
    seedRequest({ name: "Someone else's", status: "under_review", coordinator: { id: "other-id", name: "Robin" } });
    seedRequest({ name: "Waiting on organiser", status: "awaiting_clarification", coordinator: CASEY });
    const user = userEvent.setup();

    await openRequest(user, "Someone else's");
    expect(screen.queryByRole("region", { name: "Decision" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Back to review queue" }));
    await user.click(await screen.findByRole("button", { name: /Waiting on organiser/ }));
    await screen.findByRole("heading", { name: "Review request" });
    expect(screen.queryByRole("region", { name: "Decision" })).not.toBeInTheDocument();
  });

  it("shows the API's refusal and leaves the panel in place (AC 6)", async () => {
    const request = seedRequest({ name: "Alumni night", status: "under_review", coordinator: CASEY });
    server.use(
      http.post(`http://api.test/api/v1/event-requests/${request.id}/approve`, () =>
        HttpResponse.json({ code: "REQUEST_NOT_DECIDABLE", status: "approved" }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    await user.click(decision().getByRole("button", { name: "Approve request" }));

    expect(await decision().findByRole("alert")).toHaveTextContent("only be approved or rejected while it's under review");
    expect(decision().getByRole("button", { name: "Approve request" })).toBeInTheDocument();
  });
});

describe("organiser sees the outcome (US17 AC 5)", () => {
  it("shows who rejected the request, when and why", async () => {
    setDevRole("organiser");
    seedRequest({
      name: "Alumni night",
      status: "rejected",
      coordinator: CASEY,
      decided_at: "2026-10-02T03:00:00Z",
      decided_by: CASEY,
      rejection_reason: "The date clashes with exams.",
    });
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));

    await user.click(await screen.findByRole("button", { name: /Alumni night/ }));

    const outcome = await screen.findByRole("status", { name: "Decision" });
    expect(outcome).toHaveTextContent("Rejected by Casey Tan on Fri, Oct 2, 11:00 AM");
    expect(outcome).toHaveTextContent("Reason: The date clashes with exams.");
  });
});
