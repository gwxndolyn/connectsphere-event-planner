import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { COORDINATOR_PERSON, callsTo, db, seedRequest, server, startMockBackend } from "../../test/server";

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
    const queue = screen.getByRole("region", { name: "Unassigned requests" });
    // AC 2: name, organiser, preferred dates, expected attendance and status.
    expect(within(queue).getByText("Alumni night")).toBeInTheDocument();
    expect(queue).toHaveTextContent("Organiser: Olivia Organiser");
    expect(queue).toHaveTextContent("Preferred dates: 2026-11-20, 2026-11-27");
    expect(queue).toHaveTextContent("Expected attendance: 120");
    expect(queue).toHaveTextContent("submitted");
    // AC 1, 5: drafts and requests that already have a coordinator aren't queued.
    expect(screen.queryByText("A private draft")).not.toBeInTheDocument();
    expect(screen.queryByText("Already reviewed")).not.toBeInTheDocument();
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
