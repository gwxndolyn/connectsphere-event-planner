import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { COORDINATOR_PERSON, callsTo, seedCoordinatedEvent, seedRequest, server, startMockBackend } from "../../test/server";

// US10e AC 6 (SCRUM-146): the event's assigned coordinator asks the Coordinator Leads to move it, with a reason.
// Nothing moves; who is told, the statuses and the refusals are the API's (backend tests TC-US10E-21 to 24). These
// check what the review screen and the Events screen offer, send and show.
startMockBackend();

beforeEach(() => setDevRole("coordinator"));

const MINE = { id: COORDINATOR_PERSON.id, name: COORDINATOR_PERSON.name };
const SENT = "Transfer requested. The Coordinator Leads have been told.";

type User = ReturnType<typeof userEvent.setup>;

async function openReview(user: User, name: string) {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
  await screen.findByRole("heading", { level: 1, name: "Review request" });
}

async function panel() {
  return within(await screen.findByRole("region", { name: "Transfer" }));
}

describe("request a transfer (US10e AC 6)", () => {
  it("TC-US10E-29: the assigned coordinator sends a reason from the review screen; Send waits for the answer", async () => {
    const event = seedRequest({ name: "Alumni night", status: "under_review", coordinator: MINE });
    let release: () => void = () => {};
    const answered = new Promise<void>((resolve) => (release = resolve));
    server.use(
      http.post(`http://api.test/api/v1/event-requests/${event.id}/transfer-request`, async () => {
        await answered;
        return HttpResponse.json({ status: "requested" }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    await openReview(user, "Alumni night");
    const transfer = await panel();

    await user.click(transfer.getByRole("button", { name: "Request a transfer" }));
    await user.type(transfer.getByLabelText("Reason for the transfer"), "  I'm on leave that week.  ");
    await user.click(transfer.getByRole("button", { name: "Send" }));
    expect(transfer.getByRole("button", { name: "Sending…" })).toBeDisabled();

    release();
    expect(await transfer.findByRole("status")).toHaveTextContent(SENT);
    expect(transfer.queryByLabelText("Reason for the transfer")).not.toBeInTheDocument();
  });

  it("TC-US10E-30: a blank reason is refused on the field, before sending and when the API refuses it", async () => {
    const event = seedRequest({ name: "Alumni night", status: "planning", coordinator: MINE });
    const user = userEvent.setup();
    await openReview(user, "Alumni night");
    const transfer = await panel();

    await user.click(transfer.getByRole("button", { name: "Request a transfer" }));
    await user.type(transfer.getByLabelText("Reason for the transfer"), "   ");
    await user.click(transfer.getByRole("button", { name: "Send" }));
    expect(transfer.getByLabelText("Reason for the transfer")).toHaveAttribute("aria-invalid", "true");
    expect(transfer.getByRole("alert")).toHaveTextContent("Give a reason");
    expect(callsTo("POST", `/api/v1/event-requests/${event.id}/transfer-request`)).toHaveLength(0);

    server.use(
      http.post(`http://api.test/api/v1/event-requests/${event.id}/transfer-request`, () =>
        HttpResponse.json({ code: "MISSING_REQUIRED_FIELD", fields: ["reason"] }, { status: 422 }),
      ),
    );
    await user.type(transfer.getByLabelText("Reason for the transfer"), "A clash");
    expect(transfer.getByLabelText("Reason for the transfer")).not.toHaveAttribute("aria-invalid");
    await user.click(transfer.getByRole("button", { name: "Send" }));
    expect(await transfer.findByRole("alert")).toHaveTextContent("Give a reason");
    expect(transfer.getByLabelText("Reason for the transfer")).toHaveAttribute("aria-invalid", "true");
    expect(transfer.queryByRole("status")).not.toBeInTheDocument();
  });

  it("TC-US10E-31: a 409 says the event's status doesn't allow a transfer, and the form stays open", async () => {
    const event = seedRequest({ name: "Alumni night", status: "approved", coordinator: MINE });
    server.use(
      http.post(`http://api.test/api/v1/event-requests/${event.id}/transfer-request`, () =>
        HttpResponse.json({ code: "REASSIGNMENT_NOT_ALLOWED", status: "completed" }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    await openReview(user, "Alumni night");
    const transfer = await panel();

    await user.click(transfer.getByRole("button", { name: "Request a transfer" }));
    await user.type(transfer.getByLabelText("Reason for the transfer"), "I'm on leave that week.");
    await user.click(transfer.getByRole("button", { name: "Send" }));

    expect(await transfer.findByRole("alert")).toHaveTextContent("A transfer can't be requested while the event is completed.");
    expect(transfer.getByLabelText("Reason for the transfer")).toHaveValue("I'm on leave that week.");
    expect(transfer.queryByRole("status")).not.toBeInTheDocument();
  });

  it("TC-US10E-32: not offered on a cancelled event", async () => {
    seedRequest({ name: "Called off", status: "cancelled", coordinator: MINE });
    const user = userEvent.setup();
    await openReview(user, "Called off");
    expect(screen.queryByRole("region", { name: "Transfer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request a transfer" })).not.toBeInTheDocument();
  });

  it("TC-US10E-32: not offered to a coordinator the event has moved away from", async () => {
    const event = seedRequest({ name: "Moved on", status: "under_review", coordinator: MINE });
    // The request is still listed, but by the time it opens a Lead has reassigned it to someone else.
    server.use(
      http.get(`http://api.test/api/v1/event-requests/${event.id}`, () =>
        HttpResponse.json({ ...event, coordinator: { id: "other-coordinator-id", name: "Dana Lee" } }),
      ),
    );
    const user = userEvent.setup();
    await openReview(user, "Moved on");
    expect(screen.queryByRole("button", { name: "Request a transfer" })).not.toBeInTheDocument();
  });

  it("TC-US10E-33: offered on the coordinator's Events screen for a planning event, and not for a completed one", async () => {
    const event = seedCoordinatedEvent({ name: "Event Planning Demo", status: "planning" });
    seedCoordinatedEvent({ name: "Last year's fair", status: "completed" });
    const user = userEvent.setup();
    render(<App />);
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Events" }));
    await user.click(await screen.findByRole("button", { name: /Event Planning Demo/ }));
    const transfer = await panel();

    await user.click(transfer.getByRole("button", { name: "Request a transfer" }));
    await user.type(transfer.getByLabelText("Reason for the transfer"), "  I'm on leave that week.  ");
    await user.click(transfer.getByRole("button", { name: "Send" }));
    expect(await transfer.findByRole("status")).toHaveTextContent(SENT);
    expect(callsTo("POST", `/api/v1/event-requests/${event.id}/transfer-request`)[0].body).toEqual({
      reason: "I'm on leave that week.",
    });

    await user.click(screen.getByRole("button", { name: "All events" }));
    await user.click(await screen.findByRole("button", { name: /Last year's fair/ }));
    await screen.findByRole("heading", { level: 1, name: "Last year's fair" });
    expect(screen.queryByRole("region", { name: "Transfer" })).not.toBeInTheDocument();
  });
});
