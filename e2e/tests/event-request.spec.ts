import { expect, test } from "@playwright/test";

test("organiser saves, corrects, and submits an event request", async ({ page }) => {
  const preferredDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  await page.goto("/");
  await page.getByRole("button", { name: "Event requests" }).click();
  await expect(page.getByRole("heading", { name: "My event requests" })).toBeVisible();

  await page.getByRole("button", { name: "Create request" }).click();
  await page.getByLabel("Event name").fill("Neighbourhood planning workshop");
  await page.getByLabel("Event category").fill("Workshop");
  await page.getByLabel("Purpose / description").fill("Plan the next community event");
  await page.getByLabel("Preferred date").fill(preferredDate);
  await page.getByLabel("Preferred start time").fill("09:30");
  await page.getByLabel("Preferred end time").fill("11:30");

  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("status")).toContainText("Draft saved");

  await page.getByRole("button", { name: "Submit request" }).click();
  await expect(page.getByRole("alert")).toContainText("Complete the fields");
  await expect(page.locator(".request-missing")).toContainText("Expected attendees");
  await expect(page.getByLabel("Expected attendees")).toHaveAttribute("aria-invalid", "true");

  await page.getByLabel("Expected attendees").fill("32");
  await page.getByRole("button", { name: "Submit request" }).click();

  await expect(page.getByRole("heading", { level: 2, name: "Submission confirmed" })).toBeVisible();
  await expect(page.getByText(/ER-\d{4}-\d{6}/)).toBeVisible();
});