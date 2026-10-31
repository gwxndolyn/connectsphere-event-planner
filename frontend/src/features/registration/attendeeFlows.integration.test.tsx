import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../../App";
import { setDevRole } from "../../api/client";
import {
  ATTENDEE_EMAIL,
  ATTENDEE_ID,
  callsTo,
  db,
  fillSeats,
  seedEvent,
  seedRegistration,
  server,
  startMockBackend,
} from "../../test/server";

// The real App, useEventRegistry, registrationApi and apiClient against the fake backend in
// test/server.ts: each flow checks that the screens re-read the API after a change.
startMockBackend();

beforeEach(() => setDevRole("organiser"));

function card(name: string | RegExp) {
  return screen.findByRole("button", { name: typeof name === "string" ? new RegExp(name) : name });
}

function header() {
  return within(screen.getByRole("banner"));
}

function section(heading: string) {
  return screen.getByRole("heading", { name: heading }).closest(".my-events__section") as HTMLElement;
}

async function openMyEvents(user: ReturnType<typeof userEvent.setup>) {
  await user.click(header().getByRole("button", { name: "My events" }));
  await screen.findByRole("heading", { name: "My events" });
}

describe("events board", () => {
  it("lists events from the API with their seat state, sending X-Attendee-Id (TC-US3-01)", async () => {
    seedEvent({ name: "Tech Talk: Agile at Scale", capacity: 40 });
    const bootcamp = seedEvent({ name: "Design Sprint Bootcamp", capacity: 2, waitlist_enabled: true });
    fillSeats(bootcamp, 2);
    const yoga = seedEvent({ name: "Sunrise Yoga", capacity: 1 });
    fillSeats(yoga, 1);
    render(<App />);

    expect(await card("Tech Talk")).toHaveTextContent("40 seats left");
    expect(await card("Design Sprint Bootcamp")).toHaveTextContent("Full · waitlist open");
    expect(await card("Sunrise Yoga")).toHaveTextContent(/Full$/);

    const [call] = callsTo("GET", "/api/v1/events/available");
    expect(call.headers.get("X-Attendee-Id")).toBe("attendee-id");
    expect(call.headers.get("X-User-Id")).toBeNull();
  });

  it("filters by tab and by the header search, across title and venue", async () => {
    const user = userEvent.setup();
    seedEvent({ name: "Tech Talk: Agile at Scale" });
    const full = seedEvent({ name: "Design Sprint Bootcamp", capacity: 1, venue_name: "SMU Connexion", room_number: "Studio 3-2" });
    fillSeats(full, 1);
    render(<App />);
    await card("Tech Talk");

    await user.click(screen.getByRole("button", { name: "Full" }));
    expect(screen.queryByRole("button", { name: /Tech Talk/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Design Sprint Bootcamp/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByRole("button", { name: /Tech Talk/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Design Sprint Bootcamp/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "All" }));
    await user.type(screen.getByRole("searchbox", { name: "Search campus events" }), "connexion");
    expect(screen.getByRole("button", { name: /Design Sprint Bootcamp/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tech Talk/ })).not.toBeInTheDocument();

    // US24 (TC-US24-19): where the venue is matches too, though the card shows only its name.
    await user.clear(screen.getByRole("searchbox", { name: "Search campus events" }));
    await user.type(screen.getByRole("searchbox", { name: "Search campus events" }), "studio");
    expect(screen.getByRole("button", { name: /Design Sprint Bootcamp/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tech Talk/ })).not.toBeInTheDocument();

    await user.clear(screen.getByRole("searchbox", { name: "Search campus events" }));
    await user.type(screen.getByRole("searchbox", { name: "Search campus events" }), "connexion");
    await user.type(screen.getByRole("searchbox", { name: "Search campus events" }), "zzz");
    expect(screen.getByText('No events match "connexionzzz". Try another search.')).toBeInTheDocument();
  });

  it("says so when nothing is open for registration", async () => {
    render(<App />);
    expect(await screen.findByText("No events are open for registration right now.")).toBeInTheDocument();
  });

  it("explains a missing attendee id instead of a blank board", async () => {
    server.use(http.get("http://api.test/api/v1/events/available", () => HttpResponse.json({ code: "UNAUTHENTICATED" }, { status: 401 })));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Set VITE_DEV_ATTENDEE_ID");
  });

  it("reports an unreachable backend on the board and in the footer", async () => {
    server.use(http.all("http://api.test/*", () => HttpResponse.error()));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Check the backend connection");
    expect(await screen.findByText("backend unreachable")).toBeInTheDocument();
  });

  it("shows the backend's health message in the footer", async () => {
    render(<App />);
    expect(await screen.findByText("event service is up")).toBeInTheDocument();
  });
});

describe("register → My events → withdraw (US3, US11, US7)", () => {
  it("registers with the event's answers, then lists and withdraws the seat", async () => {
    const user = userEvent.setup();
    const event = seedEvent({
      name: "Tech Talk: Agile at Scale",
      capacity: 40,
      registration_fields: [
        { field_key: "dietary", label: "Dietary requirements", field_type: "text", options: null, required: true },
      ],
    });
    render(<App />);

    await user.click(await card("Tech Talk"));
    const dialog = within(screen.getByRole("dialog"));
    await user.type(dialog.getByLabelText("Dietary requirements"), "vegetarian");
    await user.click(dialog.getByRole("button", { name: "Reserve my seat" }));

    // The confirmation carries date, time and venue (TC-US3-07) and a booking reference.
    expect(await dialog.findByRole("heading", { name: "You're going!" })).toBeInTheDocument();
    expect(dialog.getByText("Fri, Oct 2, 2:00 PM – 4:00 PM")).toBeInTheDocument();
    expect(dialog.getByText("SMU SCIS Building")).toBeInTheDocument();
    expect(dialog.getByText(/^[0-9A-Z]{8}$/)).toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/events/${event.id}/registrations`)[0].body).toEqual({
      answers: { dietary: "vegetarian" },
    });

    // The board re-read the API: the seat is taken and the card says so.
    await user.click(dialog.getByRole("button", { name: "Back to events" }));
    expect(await card("Tech Talk")).toHaveTextContent("You're registered");

    // My events lists it under Confirmed with venue and room (TC-US11-02).
    await openMyEvents(user);
    const row = within(section("Confirmed")).getByRole("listitem");
    expect(row).toHaveTextContent("Tech Talk: Agile at Scale");
    expect(row).toHaveTextContent("SMU SCIS Building · Seminar Room 2-1");

    // Withdraw in two steps, then the row is gone (TC-US7-01, TC-US11-08).
    await user.click(within(row).getByRole("button", { name: "Cancel registration" }));
    const withdraw = within(screen.getByRole("dialog"));
    await user.click(withdraw.getByRole("button", { name: "Withdraw" }));
    expect(await withdraw.findByRole("heading", { name: "Withdrawal confirmed" })).toBeInTheDocument();
    await user.click(withdraw.getByRole("button", { name: "Done" }));

    const empty = await screen.findByText("You haven't registered for any upcoming events yet.");

    // And the board has the seat back on the very next read (TC-US7-13).
    await user.click(within(empty.parentElement!).getByRole("button", { name: "Browse events" }));
    expect(await card("Tech Talk")).toHaveTextContent("40 seats left");
  });

  it("flags a required answer the API says is missing (TC-US3-06)", async () => {
    const user = userEvent.setup();
    seedEvent({
      registration_fields: [
        { field_key: "tshirt", label: "T-shirt size", field_type: "select", options: ["S", "M"], required: false },
      ],
    });
    server.use(
      http.post("http://api.test/api/v1/events/:id/registrations", () =>
        HttpResponse.json({ code: "MISSING_REQUIRED_FIELD", fields: ["tshirt"] }, { status: 422 }),
      ),
    );
    render(<App />);

    await user.click(await card("Tech Talk"));
    await user.click(screen.getByRole("button", { name: "Reserve my seat" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Please answer: T-shirt size.");
    expect(screen.getByLabelText("T-shirt size")).toHaveAttribute("aria-invalid", "true");
  });

  it("shows an online event's join link in My events, not a room (TC-US11-03)", async () => {
    const event = seedEvent({
      name: "Intro to Supabase: Live Coding",
      delivery_mode: "online",
      venue_name: null,
      room_number: null,
      join_link: "https://zoom.example/j/1",
    });
    seedRegistration(event);
    const user = userEvent.setup();
    render(<App />);

    await openMyEvents(user);
    expect(within(section("Confirmed")).getByRole("link", { name: "Join online" })).toHaveAttribute(
      "href",
      "https://zoom.example/j/1",
    );
  });

  it("lists sections in order — Place available, Confirmed, Waitlisted — soonest first (TC-US11-04, 06)", async () => {
    const later = seedEvent({ name: "Later Talk", start_at: "2026-10-09T14:00:00+08:00", end_at: "2026-10-09T15:00:00+08:00" });
    const sooner = seedEvent({ name: "Sooner Talk", start_at: "2026-10-03T14:00:00+08:00", end_at: "2026-10-03T15:00:00+08:00" });
    const full = seedEvent({ name: "Bootcamp", capacity: 1, waitlist_enabled: true });
    const offered = seedEvent({ name: "Offered Talk", capacity: 1 });
    seedRegistration(later);
    seedRegistration(sooner);
    fillSeats(full, 1);
    seedRegistration(full, { attendee_id: "other-a", email: "a@smu.edu.sg", status: "waitlisted" });
    seedRegistration(full, { status: "waitlisted" });
    seedRegistration(offered, { status: "offered", offer_expires_at: "2026-10-03T01:00:00Z" });
    const user = userEvent.setup();
    render(<App />);

    await openMyEvents(user);
    expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
      "Place available",
      "Confirmed",
      "Waitlisted",
    ]);
    expect(within(section("Confirmed")).getAllByRole("listitem").map((li) => li.querySelector(".my-events__event-title")?.textContent)).toEqual([
      "Sooner Talk",
      "Later Talk",
    ]);
    expect(within(section("Waitlisted")).getByRole("listitem")).toHaveTextContent("Position 2 on the waitlist");
  });
});

describe("waitlist (US6a)", () => {
  it("joins a full event's waitlist as the logged-in attendee and shows the position on the board and in My events (TC-US6A-11)", async () => {
    const user = userEvent.setup();
    const event = seedEvent({ name: "Design Sprint Bootcamp", capacity: 2, waitlist_enabled: true });
    fillSeats(event, 2);
    seedRegistration(event, { attendee_id: null, email: "sofia@smu.edu.sg", status: "waitlisted" });
    render(<App />);

    await user.click(await card("Design Sprint Bootcamp"));
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.queryByRole("button", { name: "Reserve my seat" })).not.toBeInTheDocument();
    // SCRUM-136: nothing to type; the place is the logged-in attendee's.
    expect(dialog.queryByRole("textbox")).not.toBeInTheDocument();
    await user.click(dialog.getByRole("button", { name: "Join the waitlist" }));

    expect(await dialog.findByText("You're #2 in the queue")).toBeInTheDocument();
    const [join] = callsTo("POST", `/api/v1/events/${event.id}/waitlist`);
    expect(join.body).toEqual({});
    expect(join.headers.get("X-Attendee-Id")).toBe(ATTENDEE_ID);
    const place = db.registrations.find((r) => r.event_id === event.id && r.attendee_id === ATTENDEE_ID);
    expect(place).toMatchObject({ email: ATTENDEE_EMAIL, status: "waitlisted" });

    await user.click(dialog.getByRole("button", { name: "Back to events" }));
    expect(await card("Design Sprint Bootcamp")).toHaveTextContent("You're on the waitlist (#2)");

    await openMyEvents(user);
    expect(within(section("Waitlisted")).getByRole("listitem")).toHaveTextContent("Position 2 on the waitlist");
  });

  it("moves to the waitlist form when the last seat goes while the dialog is open", async () => {
    const user = userEvent.setup();
    const event = seedEvent({ name: "Design Sprint Bootcamp", capacity: 1, waitlist_enabled: true });
    render(<App />);
    await user.click(await card("Design Sprint Bootcamp"));

    // Someone else takes the seat after the board loaded.
    fillSeats(event, 1);
    await user.click(screen.getByRole("button", { name: "Reserve my seat" }));

    expect(await screen.findByRole("button", { name: "Join the waitlist" })).toBeInTheDocument();
    await waitFor(() => expect(callsTo("GET", "/api/v1/events/available").length).toBeGreaterThan(1));
  });

  it("leaves the waitlist from My events and everyone behind moves up (TC-US7-14)", async () => {
    const user = userEvent.setup();
    const event = seedEvent({ name: "Design Sprint Bootcamp", capacity: 1, waitlist_enabled: true });
    fillSeats(event, 1);
    seedRegistration(event, { status: "waitlisted" });
    render(<App />);

    await openMyEvents(user);
    await user.click(screen.getByRole("button", { name: "Leave waitlist" }));
    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByText(/You'll lose position 1 in the queue/)).toBeInTheDocument();
    await user.click(dialog.getByRole("button", { name: "Leave waitlist" }));
    expect(await dialog.findByRole("heading", { name: "You've left the waitlist" })).toBeInTheDocument();
    await user.click(dialog.getByRole("button", { name: "Done" }));

    expect(await screen.findByText("You haven't registered for any upcoming events yet.")).toBeInTheDocument();
  });
});

describe("offer after a withdrawal (US6b)", () => {
  it("accepts an offered place, which moves to Confirmed", async () => {
    const user = userEvent.setup();
    const event = seedEvent({ name: "Design Sprint Bootcamp", capacity: 1, waitlist_enabled: true });
    const offer = seedRegistration(event, { status: "offered", offer_expires_at: "2026-10-03T01:00:00Z" });
    render(<App />);

    await openMyEvents(user);
    const offered = within(section("Place available")).getByRole("listitem");
    expect(offered).toHaveTextContent("A seat opened up for you. Held until Sat, Oct 3, 9:00 AM.");

    await user.click(within(offered).getByRole("button", { name: "Accept place" }));
    const dialog = within(screen.getByRole("dialog"));
    await user.click(dialog.getByRole("button", { name: "Accept place" }));
    expect(await dialog.findByRole("heading", { name: "You're going!" })).toBeInTheDocument();
    expect(callsTo("POST", `/api/v1/registrations/${offer.id}/accept`)).toHaveLength(1);
    await user.click(dialog.getByRole("button", { name: "Done" }));

    expect(screen.queryByRole("heading", { name: "Place available" })).not.toBeInTheDocument();
    expect(within(section("Confirmed")).getByRole("listitem")).toHaveTextContent("Design Sprint Bootcamp");
    expect(db.registrations.find((r) => r.id === offer.id)?.status).toBe("confirmed");
  });

  it("explains an offer that lapsed before it was accepted", async () => {
    const user = userEvent.setup();
    const event = seedEvent({ name: "Design Sprint Bootcamp", capacity: 1 });
    seedRegistration(event, { status: "offered", offer_expires_at: "2026-10-03T01:00:00Z" });
    server.use(
      http.post("http://api.test/api/v1/registrations/:id/accept", () =>
        HttpResponse.json({ code: "OFFER_EXPIRED" }, { status: 409 }),
      ),
    );
    render(<App />);

    await openMyEvents(user);
    await user.click(screen.getByRole("button", { name: "Accept place" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Accept place" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("This offer has expired");
  });

  it("shows an offer that lapsed as expired, with nothing to press (SCRUM-137, TC-US7-22)", async () => {
    const user = userEvent.setup();
    const event = seedEvent({ name: "Design Sprint Bootcamp", capacity: 1 });
    seedRegistration(event, { status: "expired", offer_expires_at: "2026-10-03T01:00:00Z" });
    render(<App />);

    await openMyEvents(user);

    // Not the empty state: the expired offer is the only row, and it shows.
    expect(screen.queryByText("You haven't registered for any upcoming events yet.")).not.toBeInTheDocument();
    const expired = within(section("Offer expired")).getByRole("listitem");
    expect(expired).toHaveTextContent("Design Sprint Bootcamp");
    expect(expired).toHaveTextContent("Your offer expired at Sat, Oct 3, 9:00 AM; the place has moved on.");
    expect(expired).toHaveClass("my-events__row--expired");
    expect(within(expired).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Place available" })).not.toBeInTheDocument();
  });
});
