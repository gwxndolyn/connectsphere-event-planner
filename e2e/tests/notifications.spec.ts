import { expect, test } from "@playwright/test";

// SCRUM-107 (US31): what the system tells people lands in their Notifications view. The organiser submits, the
// Lead is told and assigns, the coordinator and the organiser are told of the assignment, and each opens the
// request from the notice and reads it. Runs against the seeded organiser, Lead and coordinator.
test("TC-US31-60: submit, assign and read the notifications each person is sent", async ({ page }) => {
  const preferredDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  // Unique per run: other specs submit requests too, and the notifications of a reused database stay.
  const eventName = `Notification workshop ${Date.now()}`;
  const notifications = page.getByRole("list", { name: "Notifications" });
  const entry = () => notifications.getByRole("listitem").filter({ hasText: eventName });
  const link = () => page.getByRole("banner").getByRole("button", { name: /^Notifications/ });

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

  // AC 1, 3, 6: the Lead's link shows unread ones, and the submission is among them, unread.
  await page.getByLabel("Acting as").selectOption("coordinator_lead");
  await expect(link()).toHaveAccessibleName(/^Notifications, \d+ unread$/);
  await link().click();
  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  await expect(entry()).toContainText("submitted request");
  await expect(entry()).toContainText("Unread");

  // AC 4: reading it takes it off the count.
  await entry().getByRole("button", { name: "Mark as read" }).click();
  await expect(entry()).not.toContainText("Unread");

  // The Lead assigns it, which tells the coordinator and the organiser.
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  const row = page.getByRole("tabpanel", { name: "Unassigned" }).locator(".assign-row", { hasText: eventName });
  await row.getByRole("button", { name: /^Assign/ }).click();
  await page.getByRole("radio").first().check();
  await page.getByRole("button", { name: "Confirm assignment" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Coordinator assigned" })).toBeVisible();

  // AC 2, 5: the coordinator's own notification, newest first, opens the request.
  await page.getByLabel("Acting as").selectOption("coordinator");
  await link().click();
  await expect(entry().first()).toContainText("You were assigned to coordinate");
  await entry().first().getByRole("button", { name: "Open request" }).click();
  await expect(page.getByRole("heading", { name: "Review request" })).toBeVisible();
  await expect(page.getByText(eventName).first()).toBeVisible();

  // The organiser is told who was assigned, and opens their request from it.
  await page.getByLabel("Acting as").selectOption("organiser");
  await link().click();
  await expect(entry().first()).toContainText("was assigned to coordinate your request");
  await entry().first().getByRole("button", { name: "Open request" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Submission confirmed" })).toBeVisible();

  // AC 4: mark all as read clears the count on the link.
  await link().click();
  await page.getByRole("button", { name: "Mark all as read" }).click();
  await expect(link()).toHaveAccessibleName("Notifications");
  await expect(notifications.locator(".notification--unread")).toHaveCount(0);
});
