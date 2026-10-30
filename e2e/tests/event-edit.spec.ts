import { expect, type Page, test } from "@playwright/test";

// US12 (SCRUM-15): the coordinator edits the seeded planning event "Event Planning Demo" (app.seed
// PLANNING_EVENT), which no other spec touches. Serial, because each step reads what the one before saved.
// Values are unique per run and a critical edit never changes the event, so a rerun works without a
// reseed; a reseed puts the event back and clears its History (docs/testing/README.md).
const EVENT = "Event Planning Demo";

test.describe.configure({ mode: "serial" });

async function openEvent(page: Page, name = EVENT) {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Events", exact: true }).click();
  await page.getByRole("region", { name: "Your events" }).getByRole("button", { name: new RegExp(name) }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
}

const stamp = Date.now().toString(36);

test("TC-US12-20: Edit is enabled for the planning event, and a confirmed one isn't listed as editable (AC 1)", async ({ page }) => {
  await openEvent(page);
  await expect(page.getByText("Planning", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit" })).toBeEnabled();

  await page.getByRole("button", { name: "All events" }).click();
  await page.getByRole("region", { name: "Your events" }).getByRole("button", { name: /Equipment Request Demo/ }).click();
  await expect(page.getByRole("button", { name: "Edit" })).toBeDisabled();
});

test("TC-US12-21: a non-critical change saves at once and the event stays in planning (AC 2)", async ({ page }) => {
  await openEvent(page);
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Equipment needs").fill(`Sticky notes ${stamp}`);
  await page.getByRole("button", { name: "Save changes" }).click();

  await expect(page.getByRole("status")).toHaveText("Your changes are saved.");
  await expect(page.getByRole("region", { name: "Event details" })).toContainText(`Sticky notes ${stamp}`);
  await page.reload();
  await page.getByRole("region", { name: "Your events" }).getByRole("button", { name: new RegExp(EVENT) }).click();
  await expect(page.getByRole("region", { name: "Event details" })).toContainText(`Sticky notes ${stamp}`);
  await expect(page.getByText("Planning", { exact: true })).toBeVisible();
});

test("TC-US12-22: a critical change waits for approval and the event keeps its capacity (AC 3)", async ({ page }) => {
  await openEvent(page);
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Capacity").fill("120");
  await page.getByRole("button", { name: "Save changes" }).click();

  await expect(page.getByRole("status")).toContainText("Your change to capacity is awaiting approval.");
  const details = page.getByRole("region", { name: "Event details" });
  await expect(details.getByText("80", { exact: true })).toBeVisible();
  await expect(page.getByRole("list", { name: "Changes awaiting approval" }).first()).toContainText("Capacity: 80 → 120");
});

test("TC-US12-23: an end before the start is refused on the end time, and History lists saves newest first (AC 4, 5)", async ({ page }) => {
  await openEvent(page);
  await page.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("End time").fill("08:00");
  await page.getByRole("button", { name: "Save changes" }).click();

  await expect(page.getByRole("alert")).toContainText("Nothing was saved.");
  await expect(page.getByText("End time must be after the start time.")).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  await page.getByRole("tab", { name: "History" }).click();
  const rows = page.getByRole("table").getByRole("row");
  // Newest first: the capacity change request, then the equipment save. The refused save left nothing.
  await expect(rows.nth(1)).toContainText("Capacity");
  await expect(rows.nth(1)).toContainText("Pending approval");
  await expect(rows.nth(2)).toContainText("Equipment needs");
  await expect(rows.nth(2)).toContainText(`Sticky notes ${stamp}`);
  await expect(rows.nth(1)).toContainText("Casey Tan");
  await expect(page.getByRole("table")).not.toContainText("08:00");
});
