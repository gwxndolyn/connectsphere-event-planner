import { expect, test } from "@playwright/test";

// SCRUM-13 (US10a): the organiser submits, the Coordinator Lead assigns from the unassigned queue,
// and the organiser then sees the coordinator's name. Runs against the seeded Lead and coordinator.
test("TC-US10A-26: the Coordinator Lead assigns a submitted request and the organiser sees the coordinator", async ({ page }) => {
  const preferredDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  // Unique per run: the queue keeps every unassigned request in a reused local database, and other
  // specs submit requests of their own.
  const eventName = `Assignment workshop ${Date.now()}`;

  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: "Create request" }).click();
  await page.getByLabel("Event name").fill(eventName);
  await page.getByLabel("Event category").fill("Workshop");
  await page.getByLabel("Purpose / description").fill("Run a planning workshop");
  await page.getByLabel("Preferred date").fill(preferredDate);
  await page.getByLabel("Preferred start time").fill("14:00");
  await page.getByLabel("Preferred end time").fill("16:00");
  await page.getByLabel("Expected attendees").fill("40");
  await page.getByRole("button", { name: "Submit request" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Submission confirmed" })).toBeVisible();

  // Submitting assigned nobody (AC 1, 8): the organiser's row says Unassigned.
  await page.getByRole("button", { name: "Back to my requests" }).first().click();
  await expect(page.getByRole("button", { name: new RegExp(eventName) })).toContainText("Coordinator: Unassigned");

  // The Lead finds it in the queue with the details needed to assign (AC 2).
  await page.getByLabel("Acting as").selectOption("coordinator_lead");
  await expect(page.getByRole("heading", { name: "Unassigned requests" })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  const queue = page.getByRole("region", { name: "Unassigned requests" });
  const row = queue.locator(".assign-row", { hasText: eventName });
  await expect(row).toContainText("Expected attendance: 40");
  await expect(row).toContainText(`Preferred dates: ${preferredDate}`);

  await row.getByRole("button", { name: /^Assign/ }).click();
  await expect(page.getByRole("heading", { name: "Assign a coordinator" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm assignment" })).toBeDisabled();
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: "Confirm assignment" }).click();

  await expect(page.getByRole("heading", { level: 2, name: "Coordinator assigned" })).toBeVisible();
  await page.getByRole("button", { name: "Back to queue" }).click();
  // AC 5: it has left the queue.
  await expect(queue.locator(".assign-row", { hasText: eventName })).toHaveCount(0);

  // The organiser now sees the coordinator and the request under review (AC 8).
  await page.getByLabel("Acting as").selectOption("organiser");
  const organiserRow = page.getByRole("button", { name: new RegExp(eventName) });
  await expect(organiserRow).toContainText("under review");
  await expect(organiserRow).not.toContainText("Unassigned");
  await expect(organiserRow).toContainText("Coordinator: Casey Tan");

  // Other roles get no Assign action (AC 6).
  await page.getByLabel("Acting as").selectOption("coordinator");
  await expect(page.getByRole("heading", { name: "Requests to review" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Assign/ })).toHaveCount(0);
});
