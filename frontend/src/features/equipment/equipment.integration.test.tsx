import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole, type DevRole } from "../../api/client";
import {
  callsTo,
  LEAD_ID,
  seedEquipmentEvent,
  seedEquipmentLine,
  seedEquipmentType,
  startMockBackend,
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

  it("explains a refused review", async () => {
    const event = seedEquipmentEvent();
    const line = seedEquipmentLine(event, seedEquipmentType("Projector"));
    const user = userEvent.setup();
    await openEquipment(user, "tech_support");
    const row = await screen.findByRole("listitem", { name: "Projector for Equipment Request Demo" });
    // Reviewed elsewhere since the queue loaded.
    line.status = "approved";

    await user.click(within(row).getByRole("button", { name: "Reject" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This line has already been reviewed (it's approved now), so it can't be changed.",
    );
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
