import { expect, test } from "@playwright/test";

// Read-only checks on the seeded board. attendee-registration.spec.ts runs alongside and moves
// Calvin's Tech Talk and Bootcamp rows, so these assert only what that spec never changes: which
// events are listed, Bootcamp being full (an offer holds its seat), Tech Talk having places, and
// Calvin's seat on the online event.
const TECH_TALK = "Tech Talk: Agile at Scale";
const BOOTCAMP = "Design Sprint Bootcamp";
const ONLINE = "Intro to Supabase: Live Coding";
// The seed's events outside the board's rule (TC-US3-01): not open yet, closed, registration
// disabled, already ended.
const NOT_LISTED = ["Startup Pitch Night", "Career Fair Prep Workshop", "Wellness Week: Sunrise Yoga", "Orientation Debrief"];

function card(page: import("@playwright/test").Page, name: string) {
  return page.getByRole("button", { name: new RegExp(name) });
}

test("the board lists only events open for registration (TC-US3-01)", async ({ page }) => {
  await page.goto("/");

  await expect(card(page, TECH_TALK)).toBeVisible();
  await expect(card(page, BOOTCAMP)).toBeVisible();
  await expect(card(page, ONLINE)).toBeVisible();
  for (const name of NOT_LISTED) {
    await expect(card(page, name)).toHaveCount(0);
  }
});

test("the Open and Full tabs split the board by seats left", async ({ page }) => {
  await page.goto("/");
  await expect(card(page, TECH_TALK)).toBeVisible();
  const tabs = page.locator(".board__tabs");

  await tabs.getByRole("button", { name: "Full" }).click();
  await expect(card(page, BOOTCAMP)).toBeVisible();
  await expect(card(page, TECH_TALK)).toHaveCount(0);
  await expect(card(page, ONLINE)).toHaveCount(0);

  await tabs.getByRole("button", { name: "Open" }).click();
  await expect(card(page, TECH_TALK)).toBeVisible();
  await expect(card(page, ONLINE)).toBeVisible();
  await expect(card(page, BOOTCAMP)).toHaveCount(0);

  await tabs.getByRole("button", { name: "All" }).click();
  await expect(card(page, BOOTCAMP)).toBeVisible();
  await expect(card(page, TECH_TALK)).toBeVisible();
});

test("the header search matches titles and venues, and says when nothing matches", async ({ page }) => {
  await page.goto("/");
  await expect(card(page, TECH_TALK)).toBeVisible();
  const search = page.getByRole("searchbox", { name: "Search campus events" });

  // Bootcamp's venue is SMU Connexion; its title doesn't say so.
  await search.fill("connexion");
  await expect(card(page, BOOTCAMP)).toBeVisible();
  await expect(card(page, TECH_TALK)).toHaveCount(0);

  await search.fill("supabase");
  await expect(card(page, ONLINE)).toBeVisible();
  await expect(card(page, BOOTCAMP)).toHaveCount(0);

  await search.fill("no such event");
  await expect(page.getByText('No events match "no such event". Try another search.')).toBeVisible();

  // Searching from My events jumps back to the board.
  await search.fill("");
  await page.getByRole("banner").getByRole("button", { name: "My events" }).click();
  await expect(page.getByRole("heading", { name: "My events" })).toBeVisible();
  await search.fill("tech");
  await expect(page.getByRole("heading", { name: "Events at ConnectSphere" })).toBeVisible();
  await expect(card(page, TECH_TALK)).toBeVisible();
});

test("an online event shows Online on the board and its join link in My events (TC-US11-03)", async ({ page }) => {
  await page.goto("/");
  const online = card(page, ONLINE);
  await expect(online).toContainText("Online");
  await expect(online).toContainText("You're registered");

  // The dialog doesn't offer a second seat.
  await online.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("You're already registered for this event. Find it under My events.");
  await expect(dialog.getByRole("button", { name: "Reserve my seat" })).toHaveCount(0);
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toHaveCount(0);

  await page.getByRole("banner").getByRole("button", { name: "My events" }).click();
  const confirmed = page.locator(".my-events__section").filter({ has: page.getByRole("heading", { name: "Confirmed" }) });
  const row = confirmed.getByRole("listitem").filter({ hasText: ONLINE });
  await expect(row.getByRole("link", { name: "Join online" })).toHaveAttribute("href", "https://smu-sg.zoom.us/j/88123345901");
});
