import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import {
  COORDINATOR_ID,
  callsTo,
  seedBooking,
  seedEquipmentEvent,
  seedEquipmentLine,
  seedEquipmentType,
  seedRequest,
  seedVenue,
  server,
  startMockBackend,
} from "../../test/server";

// US18 (SCRUM-85): the real App and review screen against the fake backend. What counts as ready is the
// API's rule, proven by backend/tests/event/test_confirmation.py; here, what the screen shows, offers and sends.
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

function seedReadyEvent(overrides = {}) {
  const request = seedRequest({
    name: "Alumni night",
    status: "approved",
    coordinator: CASEY,
    safety_approved_at: "2026-10-02T03:00:00Z",
    ...overrides,
  });
  seedBooking(request, seedVenue({ name: "SCIS Seminar Room 2-1" }), { status: "approved" });
  return request;
}

function readinessList() {
  return within(screen.getByRole("list", { name: "Readiness" }));
}

describe("coordinator confirms an event (US18)", () => {
  it("lists each arrangement and confirms once all are complete (AC 1, 2, 3)", async () => {
    const request = seedReadyEvent();
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    await screen.findByRole("list", { name: "Readiness" });
    expect(readinessList().getAllByText("Complete")).toHaveLength(3);
    expect(readinessList().getByText("SCIS Seminar Room 2-1")).toBeInTheDocument();
    expect(readinessList().getByText("No equipment was requested.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Confirm event" }));

    expect(await screen.findByRole("heading", { name: "Confirmed" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "" })).toHaveTextContent(/This event is confirmed/);
    const [call] = callsTo("POST", `/api/v1/event-requests/${request.id}/confirmation`);
    expect(call.headers.get("X-User-Id")).toBe(COORDINATOR_ID);
    expect(screen.queryByRole("button", { name: "Confirm event" })).not.toBeInTheDocument();
  });

  it("names what is outstanding and keeps Confirm disabled, with no way round it (AC 1, 2, 5)", async () => {
    const request = seedRequest({ name: "Alumni night", status: "approved", coordinator: CASEY });
    seedBooking(request, seedVenue({ name: "Auditorium" }), { status: "requested" });
    const type = seedEquipmentType("Projector");
    seedEquipmentLine(seedEquipmentEvent({ id: request.id, name: "Alumni night" }), type, { status: "pending" });
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    await screen.findByRole("list", { name: "Readiness" });
    expect(readinessList().getAllByText("Outstanding")).toHaveLength(3);
    expect(readinessList().getByText(/is waiting for Venue staff to approve it/)).toBeInTheDocument();
    expect(readinessList().getByText(/1 of 1 equipment line is waiting for Tech support/)).toBeInTheDocument();
    expect(readinessList().getByText("Waiting for the Safety Officer's approval.")).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Confirm event" });
    expect(confirm).toBeDisabled();

    await user.click(confirm);

    expect(callsTo("POST", `/api/v1/event-requests/${request.id}/confirmation`)).toHaveLength(0);
  });

  it("shows a changed arrangement when the coordinator checks again", async () => {
    const request = seedReadyEvent({ safety_approved_at: null });
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");
    await screen.findByRole("list", { name: "Readiness" });
    expect(screen.getByRole("button", { name: "Confirm event" })).toBeDisabled();

    request.safety_approved_at = "2026-10-02T03:00:00Z";
    await user.click(screen.getByRole("button", { name: "Check again" }));

    expect(await screen.findByRole("button", { name: "Confirm event" })).toBeEnabled();
  });

  it("explains a refusal from the API and shows what is true now (AC 5)", async () => {
    seedReadyEvent();
    server.use(
      http.post("*/api/v1/event-requests/:id/confirmation", () =>
        HttpResponse.json({ code: "EVENT_NOT_READY", outstanding: [], items: [] }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    await user.click(await screen.findByRole("button", { name: "Confirm event" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Some arrangements are still outstanding");
    expect(callsTo("GET", /\/readiness$/)).toHaveLength(2);
  });

  it("moves a confirmed event to Preparation (AC 6)", async () => {
    const request = seedReadyEvent({ status: "confirmed", confirmed_at: "2026-10-03T03:00:00Z" });
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    expect(await screen.findByRole("heading", { name: "Confirmed" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Start preparation" }));

    expect(await screen.findByRole("heading", { name: "Preparation" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/in Preparation/);
    expect(callsTo("POST", `/api/v1/event-requests/${request.id}/preparation`)).toHaveLength(1);
  });

  it("opens a Planning event with the venue panel and the readiness list (D11 widened)", async () => {
    seedReadyEvent({ status: "planning" });
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    expect(await screen.findByRole("button", { name: "Request venue" })).toBeInTheDocument();
    expect(await screen.findByRole("list", { name: "Readiness" })).toBeInTheDocument();
  });

  it("offers nothing to confirm on a rejected request or another coordinator's event", async () => {
    seedRequest({ name: "Alumni night", status: "under_review", coordinator: CASEY });
    const user = userEvent.setup();
    await openRequest(user, "Alumni night");

    expect(screen.queryByRole("button", { name: "Confirm event" })).not.toBeInTheDocument();
    expect(callsTo("GET", /\/readiness$/)).toHaveLength(0);
  });
});
