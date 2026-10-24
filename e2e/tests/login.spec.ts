import { expect, test, type Page } from "@playwright/test";

// US16a login, logout and session (SCRUM-105). Runs in the "login" project: a frontend built with
// VITE_DEV_AUTH unset, so login is required. Test cases: docs/testing/US16a-sign-up-log-in.md.
//
// The logged-in cases need the seeded Supabase logins (SCRUM-104, created by `python -m app.seed`
// with SUPABASE_SECRET_KEY and SEED_AUTH_PASSWORD) and that password in E2E_SEED_PASSWORD; they skip
// without it. The backend needs SUPABASE_URL to check the tokens.

const SEED_PASSWORD = process.env.E2E_SEED_PASSWORD;
const ORGANISER = "event.organiser@smu.edu.sg";
const COORDINATOR = "event.coordinator@smu.edu.sg";
const ATTENDEE = "calvin.ng.2024@smu.edu.sg";

async function logIn(page: Page, email: string, password: string) {
  await page.goto("/");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
}

// Every API call that came back 4xx/5xx, so a role's home screen can be checked for refused calls.
function failedApiCalls(page: Page): string[] {
  const failed: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("/api/v1/") && response.status() >= 400) {
      failed.push(`${response.status()} ${new URL(response.url()).pathname}`);
    }
  });
  return failed;
}

async function skipUnlessLoginIsSetUp(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
  test.skip(await page.getByText("Login isn't set up").isVisible(), "frontend/.env has no Supabase URL or key");
}

test.describe("without logging in", () => {
  test("TC-US16A-37: any screen shows the login page", async ({ page }) => {
    // As if the last screen used was My events: it still isn't shown without a login (AC 5).
    await page.addInitScript(() => localStorage.setItem("connectsphere.view", "my-events"));
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "My events" })).toHaveCount(0);
  });

  test("TC-US16A-38: no Acting as switch when VITE_DEV_AUTH is unset", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
    await expect(page.getByLabel("Acting as")).toHaveCount(0);
  });

  test("TC-US16A-34: a wrong password and an unknown email get the same message", async ({ page }) => {
    await skipUnlessLoginIsSetUp(page);

    await logIn(page, ORGANISER, "definitely-not-the-password");
    await expect(page.getByRole("alert")).toHaveText("Email or password is incorrect");

    await logIn(page, `nobody-${Date.now()}@smu.edu.sg`, "definitely-not-the-password");
    await expect(page.getByRole("alert")).toHaveText("Email or password is incorrect");
  });
});

test.describe("logged in", () => {
  test.skip(!SEED_PASSWORD, "set E2E_SEED_PASSWORD once the seeded Supabase logins exist (SCRUM-104)");

  test("TC-US16A-32: the organiser lands on Event requests", async ({ page }) => {
    const failed = failedApiCalls(page);
    await logIn(page, ORGANISER, SEED_PASSWORD!);

    await expect(page.getByRole("heading", { name: "My event requests" })).toBeVisible();
    // Staff get only their own screens: no attendee links, and no calls to the attendee routes (PR #62 review).
    const header = page.getByRole("banner");
    await expect(header.getByRole("button", { name: "My events" })).toHaveCount(0);
    await expect(header.getByRole("searchbox")).toHaveCount(0);
    await page.waitForLoadState("networkidle");
    expect(failed).toEqual([]);
  });

  test("TC-US16A-33: the coordinator lands on the review queue; an attendee on the events board", async ({ page }) => {
    const failed = failedApiCalls(page);
    await logIn(page, COORDINATOR, SEED_PASSWORD!);
    await expect(page.getByRole("heading", { name: "Requests to review" })).toBeVisible();
    await expect(page.getByRole("banner").getByRole("button", { name: "My events" })).toHaveCount(0);
    await page.waitForLoadState("networkidle");
    expect(failed).toEqual([]);

    await page.getByRole("button", { name: "Log out" }).click();
    await logIn(page, ATTENDEE, SEED_PASSWORD!);
    await expect(page.getByRole("heading", { name: "Events at ConnectSphere" })).toBeVisible();
    // Attendees get only the attendee screens.
    const header = page.getByRole("banner");
    await expect(header.getByRole("button", { name: "Event requests" })).toHaveCount(0);
    await expect(header.getByRole("button", { name: "Venues" })).toHaveCount(0);
  });

  test("TC-US16A-35: a refresh keeps the login and the screen", async ({ page }) => {
    await logIn(page, ATTENDEE, SEED_PASSWORD!);
    await page.getByRole("button", { name: "My events" }).click();
    await expect(page.getByRole("heading", { name: "My events" })).toBeVisible();

    await page.reload();

    await expect(page.getByRole("heading", { name: "My events" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Log in" })).toHaveCount(0);
  });

  test("TC-US16A-36: after logging out, protected screens show the login page", async ({ page }) => {
    await logIn(page, ATTENDEE, SEED_PASSWORD!);
    await page.getByRole("button", { name: "My events" }).click();
    await expect(page.getByRole("heading", { name: "My events" })).toBeVisible();

    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "My events" })).toHaveCount(0);
  });

  test("TC-US16A-38: no Acting as switch once logged in", async ({ page }) => {
    // The page without a login has no header at all, so this is the check that can fail (PR #62 review).
    await logIn(page, ORGANISER, SEED_PASSWORD!);
    await expect(page.getByRole("button", { name: "Log out" })).toBeVisible();

    await expect(page.getByLabel("Acting as")).toHaveCount(0);
  });

  test("TC-US16A-39: API calls carry the token and no dev headers", async ({ page }) => {
    const apiCall = page.waitForRequest((request) => request.url().includes("/api/v1/"));
    await logIn(page, ORGANISER, SEED_PASSWORD!);

    const headers = (await apiCall).headers();
    expect(headers["authorization"]).toMatch(/^Bearer \S+/);
    expect(headers["x-user-id"]).toBeUndefined();
    expect(headers["x-attendee-id"]).toBeUndefined();
  });
});
