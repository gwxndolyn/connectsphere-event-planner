import { expect, type Page, test } from "@playwright/test";

// SCRUM-84 (US17): the organiser submits, the Coordinator Lead assigns the seeded coordinator (Casey
// Tan, the dev coordinator), Casey approves or rejects, and the organiser sees the outcome. Each test
// makes its own uniquely named request, so it runs alongside the other specs.
async function submitAndAssign(page: Page, eventName: string) {
  const preferredDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: "Create request" }).click();
  await page.getByLabel("Event name").fill(eventName);
  await page.getByLabel("Event category").fill("Workshop");
  await page.getByLabel("Purpose / description").fill("Plan the term's events");
  await page.getByLabel("Preferred date").fill(preferredDate);
  await page.getByLabel("Preferred start time").fill("14:00");
  await page.getByLabel("Preferred end time").fill("16:00");
  await page.getByLabel("Expected attendees").fill("40");
  await page.getByRole("button", { name: "Submit request" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Submission confirmed" })).toBeVisible();

  await page.getByLabel("Acting as").selectOption("coordinator_lead");
  const row = page.getByRole("tabpanel", { name: "Unassigned" }).locator(".assign-row", { hasText: eventName });
  await row.getByRole("button", { name: /^Assign/ }).click();
  await page.getByRole("radio", { name: /Casey Tan/ }).check();
  await page.getByRole("button", { name: "Confirm assignment" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Coordinator assigned" })).toBeVisible();

  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("button", { name: new RegExp(eventName) }).click();
  await expect(page.getByRole("heading", { name: "Review request" })).toBeVisible();
}

async function organiserOutcome(page: Page, eventName: string) {
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("button", { name: new RegExp(eventName) }).click();
  return page.getByRole("status", { name: "Decision" });
}

test("TC-US17-16: the assigned coordinator approves and the organiser sees it (AC 1, 2, 5)", async ({ page }) => {
  const eventName = `Decision approve ${Date.now()}`;
  await submitAndAssign(page, eventName);

  await page.getByRole("region", { name: "Decision" }).getByRole("button", { name: "Approve request" }).click();
  await expect(page.getByRole("status", { name: "Decision" })).toContainText("Approved by Casey Tan");

  await expect(await organiserOutcome(page, eventName)).toContainText("Approved by Casey Tan");
});

test("TC-US17-17: a rejection needs a reason, and the organiser sees it (AC 3, 5)", async ({ page }) => {
  const eventName = `Decision reject ${Date.now()}`;
  await submitAndAssign(page, eventName);

  const decision = page.getByRole("region", { name: "Decision" });
  await decision.getByRole("button", { name: "Reject request" }).click();
  await decision.getByRole("button", { name: "Confirm rejection" }).click();
  await expect(decision.getByRole("alert")).toContainText("Give the organiser a reason");
  await decision.getByLabel("Reason for rejecting").fill("The date clashes with exams.");
  await decision.getByRole("button", { name: "Confirm rejection" }).click();
  await expect(page.getByRole("status", { name: "Decision" })).toContainText("Reason: The date clashes with exams.");

  const outcome = await organiserOutcome(page, eventName);
  await expect(outcome).toContainText("Rejected by Casey Tan");
  await expect(outcome).toContainText("Reason: The date clashes with exams.");
});
