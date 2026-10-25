import { expect, type Page, test } from "@playwright/test";

// US28 view registrations (SCRUM-96). Read-only against the seed: the seeded organiser owns the
// seeded events, and Intro to Supabase: Live Coding (capacity 200) has Calvin's confirmed seat. No
// other spec changes that event's registrations (attendee-registration.spec.ts uses Tech Talk and
// the Bootcamp), so its rows are stable here.
const ONLINE = "Intro to Supabase: Live Coding";
const CALVIN = "calvin.ng.2024@smu.edu.sg";

async function openRegistrations(page: Page, role: "organiser" | "coordinator") {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption(role);
  await page.getByRole("banner").getByRole("button", { name: "Registrations" }).click();
  await expect(page.getByRole("heading", { name: "Event registrations" })).toBeVisible();
}

function total(page: Page, label: string) {
  return page.getByLabel("Registration totals").locator("div", { has: page.getByText(label, { exact: true }) }).locator("dd");
}

test("TC-US28-16: the organiser sees totals and registrants for their seeded event (AC 1 to 3)", async ({ page }) => {
  await openRegistrations(page, "organiser");

  await page.getByRole("region", { name: "Events you manage" }).getByRole("button", { name: new RegExp(ONLINE) }).click();

  await expect(page.getByRole("heading", { level: 1, name: ONLINE })).toBeVisible();
  await expect(total(page, "Confirmed")).toHaveText("1");
  await expect(total(page, "Waitlisted")).toHaveText("0");
  await expect(total(page, "Places left")).toHaveText("199");
  const calvin = page.getByRole("table", { name: "Registrants" }).getByRole("row", { name: new RegExp(CALVIN) });
  await expect(calvin).toContainText("Confirmed");
});

test("TC-US28-17: status filter and Show all change the list, not the totals (AC 4, 5)", async ({ page }) => {
  await openRegistrations(page, "coordinator");
  await page.getByRole("region", { name: "Events you manage" }).getByRole("button", { name: new RegExp(ONLINE) }).click();
  await expect(page.getByRole("table", { name: "Registrants" })).toContainText(CALVIN);

  await page.getByLabel("Status").selectOption("waitlisted");
  await expect(page.getByText("No registrations match.")).toBeVisible();
  await expect(total(page, "Confirmed")).toHaveText("1");

  await page.getByLabel("Status").selectOption("all");
  await page.getByRole("checkbox", { name: /Show all/ }).check();
  await expect(page.getByRole("table", { name: "Registrants" })).toContainText(CALVIN);
});
