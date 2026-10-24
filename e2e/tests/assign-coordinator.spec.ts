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
  // SCRUM-67: each picker entry shows how many events that coordinator is planning.
  await expect(page.locator(".assign-picker__option").first()).toContainText(/\d+ events? planning/);
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: "Confirm assignment" }).click();

  await expect(page.getByRole("heading", { level: 2, name: "Coordinator assigned" })).toBeVisible();
  // SCRUM-69: the Lead can see who assigned whom, and when.
  await page.getByRole("button", { name: "View assignment history" }).click();
  const entry = page.getByRole("region", { name: "Assignment history" }).getByRole("listitem");
  await expect(entry).toHaveCount(1);
  await expect(entry).toContainText("Assignment");
  await expect(entry).toContainText("Lena Lim assigned");
  await expect(entry.locator("time")).toBeVisible();
  await page.getByRole("button", { name: "Back to queue" }).first().click();
  // AC 5: it has left the queue.
  await expect(queue.locator(".assign-row", { hasText: eventName })).toHaveCount(0);

  // SCRUM-86: it is now on the Lead's Assigned tab with coordinator, status and date, filterable.
  await page.getByRole("tab", { name: "Assigned", exact: true }).click();
  const assignedRow = page.getByRole("region", { name: "Assigned requests" }).locator(".assign-row", { hasText: eventName });
  await expect(assignedRow).toContainText("under review");
  await expect(assignedRow).toContainText(`Event date: ${preferredDate}`);
  await expect(assignedRow).toContainText("Coordinator: ");
  await page.getByLabel("Status").selectOption("approved");
  await expect(assignedRow).toHaveCount(0);
  await page.getByLabel("Status").selectOption("under_review");
  await expect(assignedRow).toHaveCount(1);
  await assignedRow.getByRole("button", { name: /^View/ }).click();
  await expect(page.getByRole("region", { name: "Request details" })).toContainText("Run a planning workshop");
  await page.getByRole("button", { name: "Back to queue" }).click();

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
