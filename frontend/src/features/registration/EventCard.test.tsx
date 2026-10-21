import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { makeEvent } from "../../test/fixtures";
import { EventCard } from "./EventCard";

function renderCard(props: Partial<Parameters<typeof EventCard>[0]> = {}) {
  const onReserve = vi.fn();
  render(<EventCard event={makeEvent()} waitlisted={false} onReserve={onReserve} {...props} />);
  return { onReserve, card: screen.getByRole("button") };
}

describe("EventCard", () => {
  it("shows the title, Singapore date and time, venue and seats left", () => {
    const { card } = renderCard();
    expect(card).toHaveTextContent("Tech Talk: Agile at Scale");
    expect(card).toHaveTextContent("Fri, Oct 2, 2:00 PM");
    expect(card).toHaveTextContent("SMU SCIS Building");
    expect(card).toHaveTextContent("38 seats left");
  });

  it("says 1 seat, not 1 seats", () => {
    const { card } = renderCard({ event: makeEvent({ seatsRemaining: 1 }) });
    expect(card).toHaveTextContent("1 seat left");
  });

  it("says Online instead of a venue for an online event", () => {
    const { card } = renderCard({ event: makeEvent({ format: "online", venue: undefined, joinUrl: "https://z" }) });
    expect(card).toHaveTextContent("Online");
  });

  it.each([
    [40, 40, null],
    [40, 16, "Going fast"],
    [40, 6, "Almost full"],
  ])("with %i seats of which %i are left, badges it %s", (capacity, seatsRemaining, badge) => {
    const { card } = renderCard({ event: makeEvent({ capacity, seatsRemaining }) });
    if (badge) expect(card).toHaveTextContent(badge);
    else expect(card).not.toHaveTextContent(/Going fast|Almost full/);
  });

  it("tells a full event with a waitlist apart from one without (US6a)", () => {
    const { card } = renderCard({ event: makeEvent({ isFull: true, seatsRemaining: 0, waitlistAvailable: true }) });
    expect(card).toHaveTextContent("Full · waitlist open");
  });

  it("says just Full when there's no waitlist", () => {
    const { card } = renderCard({ event: makeEvent({ isFull: true, seatsRemaining: 0, waitlistAvailable: false }) });
    expect(card).toHaveTextContent(/Full$/);
    expect(card).not.toHaveTextContent("waitlist open");
  });

  it("says You're registered for the attendee's own seat", () => {
    const { card } = renderCard({ event: makeEvent({ alreadyRegistered: true }) });
    expect(card).toHaveTextContent("You're registered");
  });

  it("shows the waitlist position ahead of already_registered (TC-US11-12)", () => {
    const { card } = renderCard({
      event: makeEvent({ alreadyRegistered: true, isFull: true }),
      waitlisted: true,
      waitlistPosition: 2,
    });
    expect(card).toHaveTextContent("You're on the waitlist (#2)");
    expect(card).not.toHaveTextContent("You're registered");
  });

  it("hands the event to onReserve when clicked", async () => {
    const event = makeEvent();
    const { onReserve, card } = renderCard({ event });
    await userEvent.click(card);
    expect(onReserve).toHaveBeenCalledWith(event);
  });
});
