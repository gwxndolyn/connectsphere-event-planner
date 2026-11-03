import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import {
  COORDINATOR_ID,
  LEAD_ID,
  ORGANISER_ID,
  TECH_SUPPORT_ID,
  VENUE_STAFF_ID,
  callsTo,
  seedNotification,
  seedRequest,
  server,
  startMockBackend,
} from "../../test/server";

// US31 (SCRUM-107): the real App against the fake backend. What a user is sent, and whether they may open
// it, is the API's rule (backend/tests/notification); here, what the link, the list and the buttons do.
startMockBackend();

type User = ReturnType<typeof userEvent.setup>;

const CASEY = { id: COORDINATOR_ID, name: "Casey Tan" };

const bannerLink = (name: RegExp | string) => within(screen.getByRole("banner")).getByRole("button", { name });

async function openNotifications(user: User, role: Parameters<typeof setDevRole>[0] = "organiser") {
  setDevRole(role);
  render(<App />);
  await user.click(await screen.findByRole("button", { name: /^Notifications/ }));
  await screen.findByRole("heading", { name: "Notifications" });
}

beforeEach(() => setDevRole("organiser"));

describe("the Notifications link (US31 AC 1, 3)", () => {
  it("TC-US31-40: is in the header on every role's screens and shows the unread count", async () => {
    seedNotification(ORGANISER_ID);
    seedNotification(ORGANISER_ID, { read: true });
    seedNotification(ORGANISER_ID);
    seedNotification(VENUE_STAFF_ID);
    const user = userEvent.setup();
    setDevRole("organiser");
    render(<App />);

    expect(await screen.findByRole("button", { name: "Notifications, 2 unread" })).toBeInTheDocument();

    // From another screen too, and each role sees its own count.
    await user.click(bannerLink("Venues"));
    expect(await screen.findByRole("button", { name: "Notifications, 2 unread" })).toBeInTheDocument();
  });

  it("TC-US31-41: shows no count when everything is read", async () => {
    seedNotification(ORGANISER_ID, { read: true });
    setDevRole("organiser");
    render(<App />);

    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /unread/ })).not.toBeInTheDocument();
  });

  it("TC-US31-42: counts only the signed-in user's, for any role", async () => {
    seedNotification(TECH_SUPPORT_ID);
    seedNotification(VENUE_STAFF_ID);
    seedNotification(VENUE_STAFF_ID);
    setDevRole("venue_staff");
    render(<App />);

    expect(await screen.findByRole("button", { name: "Notifications, 2 unread" })).toBeInTheDocument();
  });

  it("TC-US31-43: keeps the last count, without an error, when the count can't be read", async () => {
    server.use(http.get("*/api/v1/me/notifications/unread-count", () => HttpResponse.json({ code: "X" }, { status: 500 })));
    setDevRole("organiser");
    render(<App />);

    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("TC-US31-44: reads the count again when the screen changes", async () => {
    const user = userEvent.setup();
    setDevRole("organiser");
    render(<App />);
    await screen.findByRole("button", { name: "Notifications" });

    seedNotification(ORGANISER_ID);
    await user.click(bannerLink("Venues"));

    expect(await screen.findByRole("button", { name: "Notifications, 1 unread" })).toBeInTheDocument();
  });
});

describe("the Notifications screen (US31 AC 2, 3)", () => {
  it("TC-US31-45: lists my own, newest first, each with the event, what happened and when", async () => {
    seedNotification(ORGANISER_ID, { event_name: "Older event", message: "Older message", created_at: "2026-10-04T01:00:00Z", read: true });
    seedNotification(ORGANISER_ID, { event_name: "Newer event", message: "Newer message", created_at: "2026-10-04T05:00:00Z" });
    seedNotification(COORDINATOR_ID, { event_name: "Someone else's event", message: "Not mine" });
    const user = userEvent.setup();

    await openNotifications(user);

    const items = within(screen.getByRole("list", { name: "Notifications" })).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Newer event");
    expect(items[0]).toHaveTextContent("Newer message");
    expect(items[0]).toHaveTextContent(/Oct 4, \d{1,2}:\d{2}/);
    expect(items[1]).toHaveTextContent("Older event");
    expect(screen.queryByText("Not mine")).not.toBeInTheDocument();
  });

  it("TC-US31-46: marks the unread ones and says how many", async () => {
    seedNotification(ORGANISER_ID, { message: "Fresh" });
    seedNotification(ORGANISER_ID, { message: "Seen", read: true, created_at: "2026-10-03T00:00:00Z" });
    const user = userEvent.setup();

    await openNotifications(user);

    const [fresh, seen] = within(screen.getByRole("list", { name: "Notifications" })).getAllByRole("listitem");
    expect(fresh).toHaveTextContent("Unread");
    expect(fresh).toHaveClass("notification--unread");
    expect(seen).not.toHaveTextContent("Unread");
    expect(screen.getByRole("status")).toHaveTextContent("1 unread");
  });

  it("TC-US31-47: says so when there is nothing", async () => {
    const user = userEvent.setup();

    await openNotifications(user);

    expect(await screen.findByText("You have no notifications yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark all as read" })).toBeDisabled();
  });

  it("TC-US31-48: explains a list that can't be read", async () => {
    server.use(http.get("*/api/v1/me/notifications", () => HttpResponse.json({ code: "X" }, { status: 500 })));
    const user = userEvent.setup();

    await openNotifications(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("The backend rejected the request (500).");
  });
});

describe("reading them (US31 AC 4)", () => {
  it("TC-US31-49: marking one as read lowers the count on the link", async () => {
    const first = seedNotification(ORGANISER_ID, { message: "First", created_at: "2026-10-04T05:00:00Z" });
    seedNotification(ORGANISER_ID, { message: "Second", created_at: "2026-10-04T04:00:00Z" });
    const user = userEvent.setup();
    await openNotifications(user);

    const row = screen.getByText("First").closest("li") as HTMLElement;
    await user.click(within(row).getByRole("button", { name: "Mark as read" }));

    expect(await screen.findByRole("button", { name: "Notifications, 1 unread" })).toBeInTheDocument();
    expect(row).not.toHaveClass("notification--unread");
    expect(within(row).queryByRole("button", { name: "Mark as read" })).not.toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/me/notifications/${first.id}/read`)).toHaveLength(1);
  });

  it("TC-US31-50: mark all as read clears the count and the unread marks", async () => {
    seedNotification(ORGANISER_ID, { message: "One" });
    seedNotification(ORGANISER_ID, { message: "Two", created_at: "2026-10-03T00:00:00Z" });
    const user = userEvent.setup();
    await openNotifications(user);

    await user.click(screen.getByRole("button", { name: "Mark all as read" }));

    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("You're all caught up.");
    expect(document.querySelectorAll(".notification--unread")).toHaveLength(0);
    expect(callsTo("POST", "/api/v1/me/notifications/read-all")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Mark all as read" })).toBeDisabled();
  });

  it("TC-US31-51: says so when a notification can't be marked", async () => {
    seedNotification(ORGANISER_ID, { message: "One" });
    server.use(http.post("*/api/v1/me/notifications/:id/read", () => HttpResponse.json({ code: "NOT_FOUND" }, { status: 404 })));
    const user = userEvent.setup();
    await openNotifications(user);

    await user.click(screen.getByRole("button", { name: "Mark as read" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The backend rejected the request (404).");
    expect(screen.getByRole("button", { name: "Notifications, 1 unread" })).toBeInTheDocument();
  });
});

describe("opening the event (US31 AC 5)", () => {
  it("TC-US31-52: offers Open request only on a notification the user may open", async () => {
    const request = seedRequest({ name: "Alumni night", status: "approved", created_by_user_id: ORGANISER_ID });
    seedNotification(ORGANISER_ID, { message: "Openable", event_id: request.id, can_open: true, created_at: "2026-10-04T05:00:00Z" });
    seedNotification(ORGANISER_ID, { message: "Not openable", event_id: request.id, can_open: false, created_at: "2026-10-04T04:00:00Z" });
    seedNotification(ORGANISER_ID, { message: "No event", created_at: "2026-10-04T03:00:00Z" });
    const user = userEvent.setup();

    await openNotifications(user);

    const [openable, notOpenable, noEvent] = within(screen.getByRole("list", { name: "Notifications" })).getAllByRole("listitem");
    expect(within(openable).getByRole("button", { name: "Open request" })).toBeInTheDocument();
    expect(within(notOpenable).queryByRole("button", { name: "Open request" })).not.toBeInTheDocument();
    expect(within(noEvent).queryByRole("button", { name: "Open request" })).not.toBeInTheDocument();
  });

  it("TC-US31-53: opens the organiser's request, and reads the notification", async () => {
    const request = seedRequest({ name: "Alumni night", status: "approved", created_by_user_id: ORGANISER_ID, request_reference: "ER-2026-000101" });
    const note = seedNotification(ORGANISER_ID, { event_id: request.id, can_open: true });
    const user = userEvent.setup();
    await openNotifications(user);

    await user.click(screen.getByRole("button", { name: "Open request" }));

    expect((await screen.findAllByRole("heading", { name: "Submission confirmed" })).length).toBeGreaterThan(0);
    expect(screen.getAllByText("ER-2026-000101").length).toBeGreaterThan(0);
    expect(callsTo("POST", `/api/v1/me/notifications/${note.id}/read`)).toHaveLength(1);
    expect(await screen.findByRole("button", { name: "Notifications" })).toBeInTheDocument();
  });

  it("TC-US31-54: opens the coordinator's assigned request for review", async () => {
    const request = seedRequest({ name: "Alumni night", status: "under_review", coordinator: CASEY });
    seedNotification(COORDINATOR_ID, { event_id: request.id, can_open: true });
    const user = userEvent.setup();
    await openNotifications(user, "coordinator");

    await user.click(screen.getByRole("button", { name: "Open request" }));

    expect(await screen.findByRole("heading", { name: "Review request" })).toBeInTheDocument();
    expect(screen.getAllByText("Alumni night").length).toBeGreaterThan(0);
  });

  it("TC-US31-55: takes a Lead to the requests screen", async () => {
    const request = seedRequest({ name: "Alumni night", status: "submitted" });
    seedNotification(LEAD_ID, { event_id: request.id, can_open: true });
    const user = userEvent.setup();
    await openNotifications(user, "coordinator_lead");

    await user.click(screen.getByRole("button", { name: "Open request" }));

    expect(await screen.findByRole("tab", { name: /Unassigned/ })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("TC-US31-56: says so when the request is no longer the organiser's to open", async () => {
    seedNotification(ORGANISER_ID, { event_id: "gone", can_open: true });
    const user = userEvent.setup();
    await openNotifications(user);

    await user.click(screen.getByRole("button", { name: "Open request" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This request is no longer available to your account.");
  });
});
