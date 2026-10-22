import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConfirmationTicket } from "./ConfirmationTicket";

const EVENT = {
  title: "Tech Talk: Agile at Scale",
  startsAt: "2026-10-02T14:00:00+08:00",
  endsAt: "2026-10-02T16:00:00+08:00",
  venue: "SMU SCIS Building",
};

describe("ConfirmationTicket", () => {
  it("confirms a registration with date, time, venue and booking reference (TC-US3-07)", () => {
    render(
      <ConfirmationTicket
        variant="registered"
        event={EVENT}
        registrationId="3f2a9c1e-7b44-4d2a-9e10-55aa00bb11cc"
        onDone={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "You're going!" })).toBeInTheDocument();
    expect(screen.getByText("Tech Talk: Agile at Scale")).toBeInTheDocument();
    expect(screen.getByText("Fri, Oct 2, 2:00 PM – 4:00 PM")).toBeInTheDocument();
    expect(screen.getByText("SMU SCIS Building")).toBeInTheDocument();
    expect(screen.getByText("3F2A9C1E")).toBeInTheDocument();
  });

  it("links to the join link instead of a venue for an online event (TC-US3-08)", () => {
    render(
      <ConfirmationTicket
        variant="registered"
        event={{ ...EVENT, venue: undefined, joinUrl: "https://zoom.example/j/1" }}
        registrationId="abcd1234"
        onDone={vi.fn()}
      />,
    );

    expect(screen.getByRole("link", { name: "Join online" })).toHaveAttribute("href", "https://zoom.example/j/1");
  });

  it("confirms a waitlist place with the position (US6a AC 3)", () => {
    render(<ConfirmationTicket variant="waitlisted" event={EVENT} position={4} onDone={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "You're on the waitlist" })).toBeInTheDocument();
    expect(screen.getByText("You're #4 in the queue")).toBeInTheDocument();
    expect(screen.queryByText("Booking reference")).not.toBeInTheDocument();
  });

  it("calls onDone from its button, with a custom label", async () => {
    const onDone = vi.fn();
    render(<ConfirmationTicket variant="waitlisted" event={EVENT} position={1} onDone={onDone} doneLabel="Done" />);

    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onDone).toHaveBeenCalledOnce();
  });
});
