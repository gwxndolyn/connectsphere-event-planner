import { expect, test, type Page } from "@playwright/test";

// US16a sign-up (SCRUM-106). Runs in the "login" project: a frontend built with VITE_DEV_AUTH unset.
// Test cases: docs/testing/US16a-sign-up-log-in.md.
//
// "Confirm email" is on, so each case signs up a unique address, confirms it through the Supabase
// Admin API instead of an inbox, and deletes the account afterwards so the shared project doesn't fill
// with test users. Needs SUPABASE_URL and SUPABASE_SECRET_KEY (the backend's values) and E2E_SIGNUP_INBOX,
// an inbox you control that accepts plus-addressing (e.g. you@gmail.com); skips without them. Sign-ups go
// to `<inbox>+e2e-…`, so the confirmation emails Supabase still sends are delivered rather than bounced.

const SUPABASE_URL = process.env.SUPABASE_URL;
const SECRET_KEY = process.env.SUPABASE_SECRET_KEY;
const INBOX = process.env.E2E_SIGNUP_INBOX;
const PASSWORD = `E2e-${Date.now()}-pass`;

type AdminUser = { id: string; email: string; email_confirmed_at: string | null };

async function admin(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/admin${path}`, {
    ...init,
    headers: { apikey: SECRET_KEY!, Authorization: `Bearer ${SECRET_KEY}`, "Content-Type": "application/json" },
  });
  if (!response.ok) throw new Error(`Supabase Admin API ${init.method ?? "GET"} ${path}: ${response.status}`);
  return response;
}

async function findUser(email: string): Promise<AdminUser | undefined> {
  for (let page = 1; page <= 20; page++) {
    const { users } = (await (await admin(`/users?page=${page}&per_page=200`)).json()) as { users: AdminUser[] };
    const found = users.find((user) => user.email.toLowerCase() === email.toLowerCase());
    if (found || users.length === 0) return found;
  }
  return undefined;
}

function uniqueEmail(tag: string): string {
  const [local, domain] = INBOX!.split("@");
  return `${local}+e2e-${tag}-${Date.now()}@${domain}`;
}

async function signUp(page: Page, name: string, email: string, role: "Organiser" | "Attendee") {
  await page.goto("/");
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("radio", { name: role }).check();
  await page.getByRole("button", { name: "Create account" }).click();
}

async function logIn(page: Page, email: string) {
  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
}

// Every account a test makes, deleted after the run even if the test fails part-way (PR #75 review).
const created: AdminUser[] = [];

// Sign up, check the "confirm your email" state and that logging in waits for the confirmation
// (TC-US16A-50), confirm through the Admin API, log in.
async function signUpConfirmAndLogIn(page: Page, role: "Organiser" | "Attendee"): Promise<AdminUser> {
  const email = uniqueEmail(role.toLowerCase());
  await signUp(page, `E2E ${role}`, email, role);

  // Supabase answers only after the SMTP server accepts the confirmation email, which can take
  // longer than the default 5 seconds.
  await expect(page.getByText("Check your email to confirm your account")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Log out" })).toHaveCount(0);
  const user = await findUser(email);
  expect(user).toBeDefined();
  created.push(user!);
  expect(user!.email_confirmed_at).toBeFalsy();

  // Logging in before confirming says so, not "Email or password is incorrect" (PR #75 review).
  await logIn(page, email);
  await expect(page.getByRole("alert")).toHaveText("Confirm your email first: open the link we sent you, then log in.");

  await admin(`/users/${user!.id}`, { method: "PUT", body: JSON.stringify({ email_confirm: true }) });
  await logIn(page, email);
  return user!;
}

test.describe("sign up", () => {
  test.skip(
    !SUPABASE_URL || !SECRET_KEY || !INBOX,
    "set SUPABASE_URL, SUPABASE_SECRET_KEY and E2E_SIGNUP_INBOX to run the sign-up journeys",
  );

  test.afterAll(async () => {
    for (const user of created) await admin(`/users/${user.id}`, { method: "DELETE" });
  });

  test("TC-US16A-40, 45, 50: an attendee signs up, confirms, lands on the events board, and logs back in", async ({ page }) => {
    const user = await signUpConfirmAndLogIn(page, "Attendee");

    await expect(page.getByRole("heading", { name: "Events at ConnectSphere" })).toBeVisible();
    await page.getByRole("button", { name: "My events" }).click();
    await expect(page.getByText("You haven't registered for any upcoming events yet.")).toBeVisible();

    // TC-US16A-45: the same account and role after logging out and in again.
    await page.getByRole("button", { name: "Log out" }).click();
    await logIn(page, user.email);
    await expect(page.getByRole("heading", { name: "Events at ConnectSphere" })).toBeVisible();
  });

  test("TC-US16A-41: an organiser signs up, confirms and lands on Event requests", async ({ page }) => {
    await signUpConfirmAndLogIn(page, "Organiser");

    await expect(page.getByRole("heading", { name: "My event requests" })).toBeVisible();
  });

  test("TC-US16A-43: a seeded staff email is refused and nobody is logged in", async ({ page }) => {
    const before = await findUser("event.coordinator@smu.edu.sg");

    await signUp(page, "Not Staff", "event.coordinator@smu.edu.sg", "Attendee");

    await expect(page.getByRole("alert")).toHaveText("An account with this email already exists. Log in instead.");
    await expect(page.getByRole("button", { name: "Log out" })).toHaveCount(0);
    // The existing login is untouched: same account, still confirmed.
    expect(await findUser("event.coordinator@smu.edu.sg")).toEqual(before);
  });
});
