import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import { callsTo, db, seedRequest, server, startMockBackend } from "../../test/server";
import { changeFormValues, toChanges } from "./changeRequestApi";

// US29a (SCRUM-97): the real App and the organiser's request screens against the fake backend. Which fields each
// stage takes and their rules are the API's (backend/tests/event/test_change_requests.py); these check what the
// screen shows, sends and lists.
startMockBackend();

beforeEach(() => setDevRole("organiser"));

type User = ReturnType<typeof userEvent.setup>;

async function openRequest(user: User, name = "Planning workshop") {
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
  await user.click(await screen.findByRole("button", { name: new RegExp(name) }));
  return screen.findByRole("region", { name: "Change requests" });
}

describe("request a change to a submitted event (US29a)", () => {
  it("TC-US29A-19: offers Request a change from Submitted on, but not once rejected (AC 1)", async () => {
    const user = userEvent.setup();
    seedRequest({ status: "submitted" });
    seedRequest({ name: "Turned down", status: "rejected" });

    const panel = await openRequest(user);
    expect(within(panel).getByRole("button", { name: "Request a change" })).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Back to my requests" })[0]);
    await user.click(await screen.findByRole("button", { name: /Turned down/ }));
    const rejected = await screen.findByRole("region", { name: "Change requests" });
    expect(within(rejected).queryByRole("button", { name: "Request a change" })).not.toBeInTheDocument();
    expect(rejected).toHaveTextContent("Changes can't be requested once an event is rejected");
  });

  it("TC-US29A-20: shows each changed field's current and proposed value before sending, and needs a reason (AC 2, 3)", async () => {
    const user = userEvent.setup();
    seedRequest({ status: "under_review" });
    const panel = await openRequest(user);

    await user.click(within(panel).getByRole("button", { name: "Request a change" }));
    const attendees = screen.getByLabelText("Expected attendees");
    await user.clear(attendees);
    await user.type(attendees, "60");
    await user.click(screen.getByRole("button", { name: "Review change" }));

    // No reason: nothing to review yet.
    expect(screen.getByRole("alert")).toHaveTextContent("Give a reason for the change.");
    expect(screen.getByLabelText("Reason for the change")).toHaveAttribute("aria-invalid", "true");

    await user.type(screen.getByLabelText("Reason for the change"), "Two more teams are joining.");
    await user.click(screen.getByRole("button", { name: "Review change" }));
    const preview = within(screen.getByRole("region", { name: "Review your change" })).getByRole("table", { name: "Changes to send" });
    const rows = within(preview).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("Expected attendees4060");
    expect(callsTo("POST", /change-requests$/)).toHaveLength(0);
  });

  it("TC-US29A-21: sends only the changed fields with the reason; the request is Pending and the event unchanged (AC 4, 6)", async () => {
    const user = userEvent.setup();
    const request = seedRequest({ status: "under_review" });
    const panel = await openRequest(user);

    await user.click(within(panel).getByRole("button", { name: "Request a change" }));
    await user.type(screen.getByLabelText("Equipment needs"), "Two microphones");
    await user.type(screen.getByLabelText("Reason for the change"), "A panel discussion was added.");
    await user.click(screen.getByRole("button", { name: "Review change" }));
    await user.click(screen.getByRole("button", { name: "Send change request" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Change request sent.");
    expect(callsTo("POST", `/api/v1/event-requests/${request.id}/change-requests`)[0].body).toEqual({
      changes: { equipment_needs: "Two microphones" },
      reason: "A panel discussion was added.",
    });
    const list = within(panel).getByRole("list", { name: "Your change requests" });
    expect(list).toHaveTextContent("Pending");
    expect(list).toHaveTextContent("Equipment needs—Two microphones");
    expect(list).toHaveTextContent("Reason: A panel discussion was added.");
    expect(db.requests[0].equipment_needs).toBeNull();
  });

  it("TC-US29A-22: lists earlier requests with their status when the request is opened (AC 6)", async () => {
    const user = userEvent.setup();
    const request = seedRequest({ status: "approved" });
    db.changeRequests.push({
      id: "cr-1",
      event_id: request.id,
      event_name: request.name,
      request_reference: request.request_reference,
      status: "rejected",
      reason: "Bigger room",
      changes: [{ field: "expected_attendees", old_value: 40, new_value: 120 }],
      created_at: "2026-10-01T02:00:00Z",
    });

    const panel = await openRequest(user);

    const list = await within(panel).findByRole("list", { name: "Your change requests" });
    expect(list).toHaveTextContent("Rejected");
    expect(list).toHaveTextContent("Expected attendees40120");
  });

  it("TC-US29A-23: a refused field is marked with the API's message and nothing is listed (AC 2)", async () => {
    const user = userEvent.setup();
    const request = seedRequest({ status: "submitted" });
    server.use(
      http.post(`http://api.test/api/v1/event-requests/${request.id}/change-requests`, () =>
        HttpResponse.json(
          { code: "INVALID_CHANGE_REQUEST", fields: ["preferred_dates"], errors: { preferred_dates: "Preferred dates can't be in the past." } },
          { status: 422 },
        ),
      ),
    );
    const panel = await openRequest(user);

    await user.click(within(panel).getByRole("button", { name: "Request a change" }));
    await user.clear(screen.getByLabelText("Preferred date"));
    await user.type(screen.getByLabelText("Preferred date"), "2026-09-01");
    await user.type(screen.getByLabelText("Reason for the change"), "Moved earlier.");
    await user.click(screen.getByRole("button", { name: "Review change" }));
    await user.click(screen.getByRole("button", { name: "Send change request" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Nothing was sent.");
    expect(screen.getByLabelText("Preferred date")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Preferred dates can't be in the past.")).toBeInTheDocument();
    expect(within(panel).queryByRole("list", { name: "Your change requests" })).not.toBeInTheDocument();
  });
});

describe("toChanges", () => {
  it("sends a planned event's start and end, and a request's preferences, keeping its other preferred dates", () => {
    const planned = seedRequest({
      status: "planning",
      start_at: "2026-11-20T10:00:00+08:00",
      end_at: "2026-11-20T12:00:00+08:00",
    });
    const plannedForm = changeFormValues(planned);
    expect(toChanges(planned, plannedForm, { ...plannedForm, endTime: "13:00" })).toEqual({ end_at: "2026-11-20T13:00:00+08:00" });

    const requested = seedRequest({ status: "submitted", preferred_dates: ["2026-11-20", "2026-11-21"] });
    const form = changeFormValues(requested);
    expect(toChanges(requested, form, { ...form, preferred_date: "2026-11-25" })).toEqual({ preferred_dates: ["2026-11-25", "2026-11-21"] });
    expect(toChanges(requested, form, { ...form, expected_attendees: "1.5" })).toEqual({ expected_attendees: "1.5" });
  });
});
