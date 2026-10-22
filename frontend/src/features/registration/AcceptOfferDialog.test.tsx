import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { makeRegistration } from "../../test/fixtures";
import { AcceptOfferDialog } from "./AcceptOfferDialog";

const OFFER = makeRegistration({
  id: "r3",
  status: "offered",
  eventTitle: "Design Sprint Bootcamp",
  offerExpiresAt: "2026-10-03T01:00:00Z",
});

describe("AcceptOfferDialog", () => {
  it("says until when the place is held (US6b AC 1)", () => {
    render(<AcceptOfferDialog registration={OFFER} onConfirm={vi.fn()} onClose={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Take your place?" })).toBeInTheDocument();
    expect(screen.getByText(/held for you until Sat, Oct 3, 9:00 AM/)).toBeInTheDocument();
  });

  it("ends on the registration ticket once accepted (US6b AC 2)", async () => {
    const onConfirm = vi.fn().mockResolvedValue({
      registrationId: "abcdef12-0000",
      status: "confirmed",
      event: { title: "Design Sprint Bootcamp", startsAt: "2026-10-06T10:00:00+08:00", endsAt: "2026-10-06T12:00:00+08:00", venue: "SMU Connexion" },
    });
    render(<AcceptOfferDialog registration={OFFER} onConfirm={onConfirm} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Accept place" }));

    expect(await screen.findByRole("heading", { name: "You're going!" })).toBeInTheDocument();
    expect(screen.getByText("ABCDEF12")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Done" })).toBeInTheDocument();
  });

  it.each([
    ["OFFER_EXPIRED", "This offer has expired"],
    ["NO_ACTIVE_OFFER", "no longer being offered"],
  ])("explains %s and stays on the question", async (code, message) => {
    const onConfirm = vi.fn().mockRejectedValue(new ApiError(409, code));
    render(<AcceptOfferDialog registration={OFFER} onConfirm={onConfirm} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Accept place" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(screen.getByRole("heading", { name: "Take your place?" })).toBeInTheDocument();
  });

  it("closes from Not now without accepting", async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(<AcceptOfferDialog registration={OFFER} onConfirm={onConfirm} onClose={onClose} />);

    await userEvent.click(screen.getByRole("button", { name: "Not now" }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
