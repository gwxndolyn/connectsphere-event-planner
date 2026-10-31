import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { makeEvent } from "../../test/fixtures";
import { RegistrationDialog } from "./RegistrationDialog";
import type { EventAvailability } from "./types";

const CONFIRMATION = {
  registrationId: "3f2a9c1e-0000-0000-0000-000000000000",
  status: "confirmed",
  event: { title: "Tech Talk: Agile at Scale", startsAt: "2026-10-02T14:00:00+08:00", endsAt: "2026-10-02T16:00:00+08:00", venue: "SMU SCIS Building" },
};

function renderDialog(event: EventAvailability = makeEvent(), props: Partial<Parameters<typeof RegistrationDialog>[0]> = {}) {
  const handlers = {
    onRegister: vi.fn().mockResolvedValue(CONFIRMATION),
    onJoinWaitlist: vi.fn().mockResolvedValue({ registrationId: "w1", status: "waitlisted", position: 3 }),
    onRefresh: vi.fn().mockResolvedValue(undefined),
    onClose: vi.fn(),
  };
  render(<RegistrationDialog event={event} waitlisted={false} {...handlers} {...props} />);
  return { ...handlers, dialog: screen.getByRole("dialog") };
}

describe("RegistrationDialog — registering", () => {
  it("asks the event's own questions and sends the answers", async () => {
    const event = makeEvent({
      registrationFields: [
        { key: "dietary", label: "Dietary requirements", type: "text", options: null, required: false },
        { key: "tshirt", label: "T-shirt size", type: "select", options: ["S", "M", "L"], required: true },
      ],
    });
    const { onRegister } = renderDialog(event);

    await userEvent.type(screen.getByLabelText("Dietary requirements"), "vegetarian");
    await userEvent.selectOptions(screen.getByLabelText("T-shirt size"), "M");
    await userEvent.click(screen.getByRole("button", { name: "Reserve my seat" }));

    expect(onRegister).toHaveBeenCalledWith({ dietary: "vegetarian", tshirt: "M" });
    expect(await screen.findByRole("heading", { name: "You're going!" })).toBeInTheDocument();
    expect(screen.getByText("3F2A9C1E")).toBeInTheDocument();
  });

  it("flags the fields a 422 names, by their labels (TC-US3-06)", async () => {
    const event = makeEvent({
      registrationFields: [{ key: "dietary", label: "Dietary requirements", type: "text", options: null, required: false }],
    });
    const { onRegister } = renderDialog(event);
    onRegister.mockRejectedValue(new ApiError(422, "MISSING_REQUIRED_FIELD", ["dietary"]));

    await userEvent.click(screen.getByRole("button", { name: "Reserve my seat" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Please answer: Dietary requirements.");
    expect(screen.getByLabelText("Dietary requirements")).toHaveAttribute("aria-invalid", "true");
  });

  it("switches to the waitlist form when the event fills while open (EVENT_FULL with a waitlist)", async () => {
    const { onRegister, onRefresh } = renderDialog();
    onRegister.mockRejectedValue(new ApiError(409, "EVENT_FULL", [], { code: "EVENT_FULL", waitlist_available: true }));

    await userEvent.click(screen.getByRole("button", { name: "Reserve my seat" }));

    expect(await screen.findByRole("button", { name: "Join the waitlist" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onRefresh).toHaveBeenCalled();
  });

  it("explains EVENT_FULL without a waitlist instead of offering one", async () => {
    const { onRegister } = renderDialog();
    onRegister.mockRejectedValue(new ApiError(409, "EVENT_FULL", [], { code: "EVENT_FULL", waitlist_available: false }));

    await userEvent.click(screen.getByRole("button", { name: "Reserve my seat" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This event filled up");
    expect(screen.queryByRole("button", { name: "Join the waitlist" })).not.toBeInTheDocument();
  });
});

describe("RegistrationDialog — states without a form", () => {
  it("tells a registered attendee where to find it", () => {
    renderDialog(makeEvent({ alreadyRegistered: true }));
    expect(screen.getByText(/already registered for this event/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reserve my seat" })).not.toBeInTheDocument();
  });

  it("tells a waitlisted attendee where to find it", () => {
    renderDialog(makeEvent({ alreadyRegistered: true, isFull: true, waitlistAvailable: true }), { waitlisted: true });
    expect(screen.getByText("You're on the waitlist for this event. Find it under My events.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Join the waitlist" })).not.toBeInTheDocument();
  });

  it("offers nothing on a full event without a waitlist (US6a AC 2)", () => {
    renderDialog(makeEvent({ isFull: true, seatsRemaining: 0 }));
    expect(screen.getByText("This event is full.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reserve my seat|Join the waitlist/ })).not.toBeInTheDocument();
  });
});

describe("RegistrationDialog — joining a waitlist", () => {
  const FULL = makeEvent({ isFull: true, seatsRemaining: 0, waitlistAvailable: true });

  it("offers the waitlist and no seat on a full event that has one (US6a AC 1)", () => {
    renderDialog(FULL);
    expect(screen.getByRole("button", { name: "Join the waitlist" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reserve my seat" })).not.toBeInTheDocument();
    // SCRUM-136: the place is the logged-in attendee's, so nothing is typed.
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByText(/email/i)).not.toBeInTheDocument();
  });

  it("joins with one click and confirms the position (US6a AC 3, SCRUM-136)", async () => {
    const { onJoinWaitlist } = renderDialog(FULL);

    await userEvent.click(screen.getByRole("button", { name: "Join the waitlist" }));

    expect(onJoinWaitlist).toHaveBeenCalledWith();
    expect(await screen.findByText("You're #3 in the queue")).toBeInTheDocument();
  });

  it("says they're already on the list for ALREADY_REGISTERED", async () => {
    const { onJoinWaitlist } = renderDialog(FULL);
    onJoinWaitlist.mockRejectedValue(new ApiError(409, "ALREADY_REGISTERED"));

    await userEvent.click(screen.getByRole("button", { name: "Join the waitlist" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You're already registered or on the waitlist for this event.",
    );
  });

  it("refreshes when a seat came free meanwhile (SEATS_AVAILABLE)", async () => {
    const { onJoinWaitlist, onRefresh } = renderDialog(FULL);
    onJoinWaitlist.mockRejectedValue(new ApiError(409, "SEATS_AVAILABLE"));

    await userEvent.click(screen.getByRole("button", { name: "Join the waitlist" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("A seat is free now");
    expect(onRefresh).toHaveBeenCalled();
  });
});

describe("RegistrationDialog — closing", () => {
  it("closes from the × button and the overlay, not from inside the dialog", async () => {
    const { onClose, dialog } = renderDialog();

    await userEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();

    await userEvent.click(dialog.parentElement!);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
