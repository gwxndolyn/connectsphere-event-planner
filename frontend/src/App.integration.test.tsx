import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import { rememberRole } from "./auth/currentRole";
import { server, startMockBackend } from "./test/server";

// US16b AC 2 (SCRUM-121): a logged-in user's navigation follows the role they're working in. The rest
// of the suite runs in dev mode; here a Supabase session is faked so App reads GET /api/v1/me, as it
// does after a real login. Which routes each role may call is the API's (backend test_role_scope.py).
const login = vi.hoisted(() => ({ userId: "user-1" }));
vi.mock("./auth/supabase", () => ({
  DEV_AUTH: false,
  supabase: {
    auth: {
      getSession: async () => ({ data: { session: { access_token: "token", user: { id: login.userId, user_metadata: {} } } } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
      signOut: async () => ({ error: null }),
    },
  },
  accessToken: async () => "token",
}));

startMockBackend();

/** GET /api/v1/me answers with only `roles` since SCRUM-121 (TC-US16B-27). */
function loggedInAs(roles: string[]) {
  server.use(
    http.get("http://api.test/api/v1/me", () =>
      HttpResponse.json({ id: login.userId, email: "morgan.lau@smu.edu.sg", full_name: "Morgan Lau", roles }),
    ),
  );
}

async function header() {
  return within(await screen.findByRole("banner"));
}

describe("role switcher (US16b AC 2)", () => {
  it("gives a user with one role no switcher and their home screen (TC-US16B-17)", async () => {
    loggedInAs(["coordinator"]);
    render(<App />);

    expect((await header()).getByRole("button", { name: "Event requests" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByLabelText("Role")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Acting as")).not.toBeInTheDocument();
  });

  it("starts a two-role user on their first role, with only its screens (TC-US16B-18)", async () => {
    loggedInAs(["coordinator", "venue_staff"]);
    render(<App />);

    const nav = await header();
    expect(nav.getByLabelText("Role")).toHaveValue("coordinator");
    expect(nav.getByRole("button", { name: "Event requests" })).toHaveAttribute("aria-current", "page");
    expect(nav.getAllByRole("button").map((button) => button.textContent)).toEqual([
      "ConnectSphere",
      "Event requests",
      "Registrations",
      "Venues",
      "Equipment",
      "Log out",
    ]);
  });

  it("switches to Venue staff's screens and keeps them after a refresh (TC-US16B-19)", async () => {
    loggedInAs(["coordinator", "venue_staff"]);
    const user = userEvent.setup();
    const { unmount } = render(<App />);

    await user.selectOptions((await header()).getByLabelText("Role"), "Venue staff");

    const nav = await header();
    expect(nav.queryByRole("button", { name: "Event requests" })).not.toBeInTheDocument();
    expect(nav.getByRole("button", { name: "Venues" })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("heading", { name: "Pending venue requests" })).toBeInTheDocument();

    unmount();
    render(<App />);
    expect((await header()).getByLabelText("Role")).toHaveValue("venue_staff");
    expect((await header()).getByRole("button", { name: "Venues" })).toHaveAttribute("aria-current", "page");
  });

  it("starts on the first held role when the stored one is another user's or no longer held (TC-US16B-20)", async () => {
    rememberRole("someone-else", "venue_staff");
    loggedInAs(["coordinator", "venue_staff"]);
    const { unmount } = render(<App />);
    expect((await header()).getByLabelText("Role")).toHaveValue("coordinator");
    unmount();

    rememberRole(login.userId, "tech_support");
    render(<App />);
    expect((await header()).getByLabelText("Role")).toHaveValue("coordinator");
  });

  it("opens the role's home screen instead of a stored screen it doesn't have (TC-US16B-20)", async () => {
    localStorage.setItem("connectsphere.view", "equipment");
    loggedInAs(["venue_staff"]);
    render(<App />);

    expect((await header()).getByRole("button", { name: "Venues" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("button", { name: "Equipment" })).not.toBeInTheDocument();
  });

  it("tells a Safety officer their role has no screens yet, with Log out (TC-US16B-21)", async () => {
    loggedInAs(["safety_officer"]);
    render(<App />);

    expect(await screen.findByText("Your account's role doesn't have any screens yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
  });
});
