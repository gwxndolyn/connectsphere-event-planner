import { expect, test } from "@playwright/test";

// SCRUM-85 (US18): the seeded coordinator (Casey Tan, the dev coordinator) opens the approved event
// "Confirmation Demo" (app.seed CONFIRMATION_EVENT), which has an approved venue booking and the Safety
// Officer's approval, sees every arrangement complete, confirms it, and starts Preparation. No other spec
// touches it. Confirming changes the event for good, so rerunning on the same database needs a reseed
// (`python -m app.seed`), which puts the demo back to Approved.
const EVENT = "Confirmation Demo";

test("TC-US18-30: the coordinator confirms a ready event, then starts Preparation (AC 1-3, 6)", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await expect(page.getByRole("heading", { name: "Review request" })).toBeVisible();

  const readiness = page.getByRole("list", { name: "Readiness" });
  await expect(readiness).toBeVisible();
  await expect(readiness.getByText("Complete")).toHaveCount(3);
  await expect(readiness).toContainText("Li Ka Shing Library Seminar Room 3-4");

  await page.getByRole("button", { name: "Confirm event" }).click();
  await expect(page.getByRole("heading", { name: "Confirmed" })).toBeVisible();

  await page.getByRole("button", { name: "Start preparation" }).click();
  await expect(page.getByRole("heading", { name: "Preparation" })).toBeVisible();
});
