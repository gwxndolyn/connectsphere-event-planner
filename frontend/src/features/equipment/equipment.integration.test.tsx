import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole, type DevRole } from "../../api/client";
import {
  callsTo,
  LEAD_ID,
  seedEquipmentEvent,
  seedEquipmentLine,
  seedEquipmentType,
  server,
  setAvailability,
  startMockBackend,
  TECH_SUPPORT_ID,
} from "../../test/server";

// US26 screens (SCRUM-110): the real App, the coordinator's Equipment screen and Tech Support's queue
// against the fake backend. The rules (who may, which events, one live line per type) are SCRUM-109's,
// tested in backend/tests/equipment/test_equipment_api.py; e2e/tests/equipment.spec.ts runs TC-US26-16
// and 17 against the real API. These tests check what the screens send and show.
startMockBackend();

type User = ReturnType<typeof userEvent.setup>;

async function openEquipment(user: User, role: DevRole) {
  setDevRole(role);
  render(<App />);
  await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Equipment" }));
}

async function pickEvent(user: User, name: string) {
  await user.selectOptions(await screen.findByLabelText("Event"), name);
}

function lines() {
  return within(screen.getByRole("list", { name: "Equipment lines" }));
}

function addForm() {
  return within(screen.getByRole("region", { name: "Add equipment" }));
}

describe("coordinator's equipment (US26 AC 1, 2, 4)", () => {
  it("lists only the coordinator's planning and confirmed events, soonest first (TC-US26-20)", async () => {
    seedEquipmentEvent({ name: "Career Fair", status: "planning", start_at: "2026-11-20T02:00:00Z" });
    seedEquipmentEvent({ name: "Equipment Request Demo", start_at: "2026-11-07T02:00:00Z" });
    seedEquipmentEvent({ name: "Approved Only", status: "approved" });
    seedEquipmentEvent({ name: "Someone Else's", coordinator_id: LEAD_ID });
    const user = userEvent.setup();
    await openEquipment(user, "coordinator");

    const picker = await screen.findByLabelText("Event");
    const options = within(picker)
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(options).toEqual(["Choose an event", "Equipment Request Demo", "Career Fair"]);
    expect(callsTo("GET", "/api/v1/me/equipment-events")[0].headers.get("X-User-Id")).toBe("coordinator-id");
  });

  it("says so when none of the coordinator's events can take equipment", async () => {
    seedEquipmentEvent({ status: "approved" });
    const user = userEvent.setup();
    await openEquipment(user, "coordinator");

    expect(
      await screen.findByText(
        "None of your events can take equipment requests yet. Only planning or confirmed events assigned to you are listed.",
      ),
    ).toBeInTheDocument();
  });

  it("shows only the error when the events can't load, not the empty-list message (PR #78 review)", async () => {
    seedEquipmentEvent();
    server.use(
      http.get("http://api.test/api/v1/me/equipment-events", () => HttpResponse.json({ detail: "boom" }, { status: 500 })),
    );
    const user = userEvent.setup();
    await openEquipment(user, "coordinator");

    expect(await screen.findByRole("alert")).toHaveTextContent("The request could not be completed.");
    expect(screen.queryByText(/None of your events can take equipment requests yet/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Event")).not.toBeInTheDocument();
  });

  it("clears an earlier error once a line is added (PR #78 review)", async () => {
    seedEquipmentEvent();
    seedEquipmentType("Projector");
    // The event's lines fail to load once, then the coordinator adds a line anyway.
    server.use(
      http.get("http://api.test/api/v1/events/:id/equipment-lines", () => HttpResponse.json({ detail: "boom" }, { status: 500 }), {
        once: true,
      }),
    );
    const user = userEvent.setup();
    await openEquipment(user, "coordinator");
    await pickEvent(user, "Equipment Request Demo");
    expect(await screen.findByRole("alert")).toHaveTextContent("The request could not be completed.");

    await user.selectOptions(addForm().getByLabelText("Equipment type"), "Projector");
    await user.type(addForm().getByLabelText("Quantity"), "2");
    await user.click(addForm().getByRole("button", { name: "Add line" }));

    expect(await lines().findByRole("listitem", { name: "Projector" })).toHaveTextContent("Pending");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("adds a line: the quantity error shows on the field, and once fixed the line is Pending (TC-US26-16)", async () => {
    seedEquipmentEvent();
    const projector = seedEquipmentType("Projector");
    seedEquipmentType("HDMI cable");
    const user = userEvent.setup();
    await openEquipment(user, "coordinator");
    await pickEvent(user, "Equipment Request Demo");
    expect(await screen.findByText("No equipment requested for this event yet.")).toBeInTheDocument();

    await user.selectOptions(addForm().getByLabelText("Equipment type"), "Projector");
    await user.type(addForm().getByLabelText("Quantity"), "0");
    await user.click(addForm().getByRole("button", { name: "Add line" }));

    const quantity = addForm().getByLabelText("Quantity");
    expect(await addForm().findByText("Quantity must be a whole number of at least 1.")).toBeInTheDocument();
    expect(quantity).toHaveAccessibleDescription("Quantity must be a whole number of at least 1.");
    expect(quantity).toHaveAttribute("aria-invalid", "true");

    await user.clear(quantity);
    await user.type(quantity, "2");
    await user.type(addForm().getByLabelText("Notes"), "Front of the room");
    await user.click(addForm().getByRole("button", { name: "Add line" }));

    const row = await lines().findByRole("listitem", { name: "Projector" });
    expect(row).toHaveTextContent("Pending");
    expect(row).toHaveTextContent("Quantity 2");
    expect(row).toHaveTextContent("Front of the room");
    expect(addForm().getByLabelText("Quantity")).toHaveValue(null);

    const sent = callsTo("POST", /\/equipment-lines$/);
    expect(sent.map((call) => call.body)).toEqual([
      { equipment_type_id: projector.id, quantity: 0, notes: null },
      { equipment_type_id: projector.id, quantity: 2, notes: "Front of the room" },
    ]);
    expect(sent[1].headers.get("X-User-Id")).toBe("coordinator-id");
  });

  it("edits a pending line and removes another after asking (TC-US26-16)", async () => {
    const event = seedEquipmentEvent();
    const projector = seedEquipmentType("Projector");
    const cable = seedEquipmentType("HDMI cable");
    const line = seedEquipmentLine(event, projector, { quantity: 2 });
    const other = seedEquipmentLine(event, cable, { quantity: 1 });
    const user = userEvent.setup();
    await openEquipment(user, "coordinator");
    await pickEvent(user, "Equipment Request Demo");

    await user.click(within(await lines().findByRole("listitem", { name: "Projector" })).getByRole("button", { name: "Edit" }));
    const editing = within(screen.getByRole("form", { name: "Edit Projector" }));
    await user.clear(editing.getByLabelText("Quantity"));
    await user.type(editing.getByLabelText("Quantity"), "3");
    await user.type(editing.getByLabelText("Notes"), "One spare");
    await user.click(editing.getByRole("button", { name: "Save" }));

    const edited = await lines().findByRole("listitem", { name: "Projector" });
    expect(await within(edited).findByText("Quantity 3")).toBeInTheDocument();
    expect(edited).toHaveTextContent("One spare");
    expect(callsTo("PATCH", `/api/v1/equipment-lines/${line.id}`)[0].body).toEqual({
      equipment_type_id: projector.id,
      quantity: 3,
      notes: "One spare",
    });

    await user.click(within(lines().getByRole("listitem", { name: "HDMI cable" })).getByRole("button", { name: "Remove" }));
    const dialog = within(screen.getByRole("dialog", { name: "Remove this equipment line?" }));
    expect(callsTo("DELETE", `/api/v1/equipment-lines/${other.id}`)).toHaveLength(0);
    await user.click(dialog.getByRole("button", { name: "Remove line" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Removed: HDMI cable");
    expect(lines().queryByRole("listitem", { name: "HDMI cable" })).not.toBeInTheDocument();
    expect(callsTo("DELETE", `/api/v1/equipment-lines/${other.id}`)).toHaveLength(1);
  });

  it("shows a reviewed line's decision and note, with no Edit or Remove (TC-US26-17)", async () => {
    const event = seedEquipmentEvent();
    seedEquipmentLine(event, seedEquipmentType("Wireless microphone"), {
      status: "approved",
      review_note: "Two from the AV store",
      reviewed_by_user_id: "tech-support-id",
      reviewed_at: "2026-10-02T02:00:00Z",
    });
    const user = userEvent.setup();
    await openEquipment(user, "coordinator");
    await pickEvent(user, "Equipment Request Demo");

    const row = await lines().findByRole("listitem", { name: "Wireless microphone" });
    expect(row).toHaveTextContent("Approved");
    expect(row).toHaveTextContent("Tech support: Two from the AV store");
    expect(within(row).queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(within(row).queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
  });

  it("shows the API's duplicate-type refusal on the type field (TC-US26-19)", async () => {
    const event = seedEquipmentEvent();
    seedEquipmentLine(event, seedEquipmentType("Projector"));
    const user = userEvent.setup();
    await openEquipment(user, "coordinator");
    await pickEvent(user, "Equipment Request Demo");
    await lines().findByRole("listitem", { name: "Projector" });

    await user.selectOptions(addForm().getByLabelText("Equipment type"), "Projector");
    await user.type(addForm().getByLabelText("Quantity"), "1");
    await user.click(addForm().getByRole("button", { name: "Add line" }));

    expect(await addForm().findByText(/already has a pending or approved line for that equipment type/)).toBeInTheDocument();
    expect(addForm().getByLabelText("Equipment type")).toHaveAttribute("aria-invalid", "true");
    expect(lines().getAllByRole("listitem")).toHaveLength(1);
  });
});

describe("Tech Support's queue (US26 AC 3)", () => {
  it("approves a pending line with a note, and it leaves the queue (TC-US26-17)", async () => {
    const demo = seedEquipmentEvent();
    const fair = seedEquipmentEvent({ name: "Career Fair", status: "planning", start_at: "2026-11-20T02:00:00Z" });
    const line = seedEquipmentLine(demo, seedEquipmentType("Projector"), { notes: "Front of the room" });
    const laptop = seedEquipmentLine(fair, seedEquipmentType("Laptop"), { quantity: 1 });
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");

    expect(await screen.findByRole("heading", { name: "Equipment requests to review" })).toBeInTheDocument();
    const row = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });
    expect(row).toHaveTextContent("Sat, Nov 7");
    expect(row).toHaveTextContent("Quantity 2");
    expect(row).toHaveTextContent("Front of the room");

    await user.type(within(row).getByLabelText("Note"), "Two from the AV store");
    await user.click(within(row).getByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Approved: Projector for Equipment Request Demo.");
    expect(screen.queryByRole("listitem", { name: "Projector for Equipment Request Demo" })).not.toBeInTheDocument();
    const [review] = callsTo("POST", `/api/v1/equipment-lines/${line.id}/review`);
    expect(review.body).toEqual({ decision: "approved", note: "Two from the AV store" });
    expect(review.headers.get("X-User-Id")).toBe("tech-support-id");

    // Rejecting without a note is allowed (D43).
    await user.click(within(screen.getByRole("listitem", { name: "Laptop for Career Fair" })).getByRole("button", { name: "Reject" }));
    expect(await screen.findByText("No equipment requests are waiting for review.")).toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/equipment-lines/${laptop.id}/review`)[0].body).toEqual({ decision: "rejected" });
  });

  it("doesn't approve a line the coordinator changed since the queue loaded, and shows the change (PR #78 review)", async () => {
    const event = seedEquipmentEvent();
    const line = seedEquipmentLine(event, seedEquipmentType("Projector"), { quantity: 2 });
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");
    const row = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });
    expect(row).toHaveTextContent("Quantity 2");
    // The coordinator edits it while Tech support has the queue open: approval is always the full
    // quantity (AC 6), so approving now would approve 10, not the 2 on screen.
    Object.assign(line, { quantity: 10, updated_at: "2026-10-03T02:00:00Z" });

    await user.click(within(row).getByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Projector for Equipment Request Demo changed since you loaded it: it's now Quantity 10. Check it, then choose again.",
    );
    expect(callsTo("POST", `/api/v1/equipment-lines/${line.id}/review`)).toHaveLength(0);
    const changed = screen.getByRole("listitem", { name: "Projector for Equipment Request Demo" });
    expect(changed).toHaveTextContent("Quantity 10");

    // Seen now, so a second click approves it.
    await user.click(within(changed).getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Approved: Projector for Equipment Request Demo.");
    expect(callsTo("POST", `/api/v1/equipment-lines/${line.id}/review`)).toHaveLength(1);
  });

  it("doesn't review a line that left the queue since it loaded", async () => {
    const event = seedEquipmentEvent();
    const line = seedEquipmentLine(event, seedEquipmentType("Projector"));
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");
    const row = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });
    // Reviewed elsewhere, or removed by the coordinator, since the queue loaded.
    line.status = "approved";

    await user.click(within(row).getByRole("button", { name: "Reject" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Projector for Equipment Request Demo is no longer waiting for review: it was reviewed, or the coordinator removed it.",
    );
    expect(callsTo("POST", `/api/v1/equipment-lines/${line.id}/review`)).toHaveLength(0);
    expect(screen.queryByRole("listitem", { name: "Projector for Equipment Request Demo" })).not.toBeInTheDocument();
  });

  it("explains a review the API refuses", async () => {
    const event = seedEquipmentEvent();
    seedEquipmentLine(event, seedEquipmentType("Projector"));
    // Reviewed by someone else between the check and the review.
    server.use(
      http.post("http://api.test/api/v1/equipment-lines/:id/review", () =>
        HttpResponse.json({ code: "LINE_NOT_PENDING", status: "approved" }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");
    const row = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });

    await user.click(within(row).getByRole("button", { name: "Reject" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This line has already been reviewed (it's approved now), so it can't be changed.",
    );
  });
});

describe("checking availability (US5, SCRUM-126)", () => {
  it("shows the check's result on the row; the line's status and Approve / Reject stay (TC-US5-12)", async () => {
    const event = seedEquipmentEvent();
    const projector = seedEquipmentLine(event, seedEquipmentType("Projector"), { quantity: 4 });
    setAvailability(projector, {
      equipment_type: { id: projector.equipment_type.id, name: "Projector", storage_location: "AV store, Level B1" },
      total: 10,
      out_of_service: 2,
      reserved_elsewhere: 3,
      available: 5,
    });
    const speakers = seedEquipmentLine(event, seedEquipmentType("Speaker system"), { quantity: 5 });
    setAvailability(speakers, { total: 3, out_of_service: 1, available: 2 });
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");
    const row = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });

    await user.click(within(row).getByRole("button", { name: "Check availability" }));

    const result = await within(row).findByRole("region", { name: "Availability" });
    expect(result).toHaveTextContent("5 available for 4 requested: Sufficient");
    expect(result).toHaveTextContent("Stock 10 · Out of service 2 · Reserved for other events 3");
    expect(result).toHaveTextContent("Stored at AV store, Level B1");
    const [check] = callsTo("POST", `/api/v1/equipment-lines/${projector.id}/availability-check`);
    expect(check.headers.get("X-User-Id")).toBe("tech-support-id");
    // A check only (AC 5): the line stays in the queue with its review buttons, and nothing is reviewed.
    expect(within(row).getByRole("button", { name: "Approve" })).toBeEnabled();
    expect(within(row).getByRole("button", { name: "Reject" })).toBeEnabled();
    expect(callsTo("POST", `/api/v1/equipment-lines/${projector.id}/review`)).toHaveLength(0);

    const short = screen.getByRole("listitem", { name: "Speaker system for Equipment Request Demo" });
    await user.click(within(short).getByRole("button", { name: "Check availability" }));
    const shortResult = await within(short).findByRole("region", { name: "Availability" });
    expect(shortResult).toHaveTextContent("2 available for 5 requested: Short by 3");
    expect(shortResult).toHaveTextContent("Storage location not recorded");
  });

  it("shows a failed check on that row only (TC-US5-12)", async () => {
    const event = seedEquipmentEvent();
    const projector = seedEquipmentLine(event, seedEquipmentType("Projector"));
    seedEquipmentLine(event, seedEquipmentType("Laptop"));
    server.use(
      http.post(`http://api.test/api/v1/equipment-lines/${projector.id}/availability-check`, () =>
        HttpResponse.json({ code: "NOT_FOUND" }, { status: 404 }),
      ),
    );
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");
    const row = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });

    await user.click(within(row).getByRole("button", { name: "Check availability" }));

    expect(await within(row).findByRole("alert")).toHaveTextContent(
      "This event or equipment line is no longer available. Reload and try again.",
    );
    const other = screen.getByRole("listitem", { name: "Laptop for Equipment Request Demo" });
    expect(within(other).queryByRole("alert")).not.toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Approve" })).toBeEnabled();
  });

  it("shows each line's last recorded check, and none for a line never checked (TC-US5-15)", async () => {
    const event = seedEquipmentEvent();
    seedEquipmentLine(event, seedEquipmentType("Projector"), {
      availability_check: {
        sufficient: false,
        shortfall: 2,
        checked_by_user_id: TECH_SUPPORT_ID,
        checked_at: "2026-10-02T01:30:00Z",
      },
    });
    seedEquipmentLine(event, seedEquipmentType("Laptop"));
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");

    const checked = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });
    expect(checked).toHaveTextContent("Last checked Fri, Oct 2, 9:30 AM: Short by 2");
    const unchecked = screen.getByRole("listitem", { name: "Laptop for Equipment Request Demo" });
    expect(unchecked).not.toHaveTextContent("Last checked");
  });

  it("approves a line just checked, without saying it changed (TC-US5-15)", async () => {
    // Recording the check updates the line on the server; the queue must not take that for the
    // coordinator's edit that Approve guards against (PR #78 review).
    const event = seedEquipmentEvent();
    const line = seedEquipmentLine(event, seedEquipmentType("Projector"));
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");
    const row = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });
    await user.click(within(row).getByRole("button", { name: "Check availability" }));
    expect(await within(row).findByText(/Last checked .*: Sufficient/)).toBeInTheDocument();

    await user.click(within(screen.getByRole("listitem", { name: "Projector for Equipment Request Demo" })).getByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Approved: Projector for Equipment Request Demo.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/equipment-lines/${line.id}/review`)).toHaveLength(1);
  });
});

describe("no one reviews their own line (US16b D51, SCRUM-121)", () => {
  it("Approve or Reject on a line Tech support requested says who must review it, and the row stays (TC-US16B-30)", async () => {
    // A Tech support user who is also a Coordinator requested this one (D51 refuses it on the API).
    seedEquipmentLine(seedEquipmentEvent(), seedEquipmentType("Projector"), { requested_by_user_id: TECH_SUPPORT_ID });
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");
    const row = () => screen.getByRole("listitem", { name: "Projector for Equipment Request Demo" });
    await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });

    for (const decision of ["Approve", "Reject"]) {
      await user.click(within(row()).getByRole("button", { name: decision }));
      expect(await within(row()).findByRole("alert")).toHaveTextContent(
        "Another Tech support user must review this line, because you requested it or coordinate its event.",
      );
    }
    expect(callsTo("POST", /\/review$/)).toHaveLength(2);
  });
});

describe("Equipment for other roles (dev mode)", () => {
  it("tells other roles it's for Coordinators and Tech support, and Tech support that Event requests aren't theirs", async () => {
    const user = userEvent.setup();
    await openEquipment(user, "organiser");
    expect(
      await screen.findByText("Equipment requests are for Coordinators and Tech support. Switch Acting as to see them."),
    ).toBeInTheDocument();
    expect(callsTo("GET", "/api/v1/me/equipment-events")).toHaveLength(0);

    await user.selectOptions(screen.getByLabelText("Acting as"), "Tech support");
    await user.click(within(screen.getByRole("banner")).getByRole("button", { name: "Event requests" }));
    expect(
      await screen.findByText("Event requests aren't part of the Tech support role. Switch Acting as to see them."),
    ).toBeInTheDocument();
  });
});
