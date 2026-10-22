import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { makeRegistration } from "../../test/fixtures";
import { WithdrawDialog } from "./WithdrawDialog";

const RESULT = { status: "withdrawn", withdrawnAt: "2026-10-01T02:05:00Z", eventTitle: "Tech Talk: Agile at Scale", seatsRemaining: 4 };

describe("WithdrawDialog", () => {
  it("asks before withdrawing a confirmed seat, then confirms it (SCRUM-38)", async () => {
    const onConfirm = vi.fn().mockResolvedValue(RESULT);
    render(<WithdrawDialog registration={makeRegistration()} onConfirm={onConfirm} onClose={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Withdraw from this event?" })).toBeInTheDocument();
    expect(screen.getByText(/offered to the next person on the waitlist/)).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Withdraw" }));

    expect(await screen.findByRole("heading", { name: "Withdrawal confirmed" })).toBeInTheDocument();
    expect(screen.getByText("Withdrawn at 10:05 AM")).toBeInTheDocument();
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("words a waitlist exit as leaving the queue, with the position at stake (TC-US7-14)", async () => {
    const onConfirm = vi.fn().mockResolvedValue(RESULT);
    render(
      <WithdrawDialog
        registration={makeRegistration({ status: "waitlisted", waitlistPosition: 2 })}
        onConfirm={onConfirm}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Leave this waitlist?" })).toBeInTheDocument();
    expect(screen.getByText(/You'll lose position 2 in the queue/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Leave waitlist" }));
    expect(await screen.findByRole("heading", { name: "You've left the waitlist" })).toBeInTheDocument();
  });

  it("keeps the dialog open with the reason when the API refuses (TC-US7-03)", async () => {
    const onConfirm = vi.fn().mockRejectedValue(new ApiError(403, "EVENT_STARTED"));
    render(<WithdrawDialog registration={makeRegistration()} onConfirm={onConfirm} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Withdraw" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This event has already started");
    expect(screen.queryByRole("heading", { name: "Withdrawal confirmed" })).not.toBeInTheDocument();
  });

  it("closes without withdrawing from Keep my seat", async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(<WithdrawDialog registration={makeRegistration()} onConfirm={onConfirm} onClose={onClose} />);

    await userEvent.click(screen.getByRole("button", { name: "Keep my seat" }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
