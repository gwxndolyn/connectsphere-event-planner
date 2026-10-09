import { expect, test } from "@playwright/test";

test("coordinator asks for clarification and the organiser answers it", async ({ page }) => {
  const preferredDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  // Unique per run: the review queue keeps every submitted request in a reused local database.
  const eventName = `Clarification workshop ${Date.now()}`;

  // The organiser submits a complete request.
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

  // The coordinator finds it in the review queue.
  await page.getByLabel("Acting as").selectOption("coordinator");
  await expect(page.getByRole("heading", { name: "Requests to review" })).toBeVisible();
  await page.getByRole("button", { name: new RegExp(eventName) }).click();
  await expect(page.getByRole("heading", { name: "Review request" })).toBeVisible();
  await expect(page.getByText("40", { exact: true })).toBeVisible();

  // Sending with nothing chosen is refused and both inputs are flagged.
  await page.getByRole("button", { name: "Send clarification request" }).click();
  await expect(page.getByRole("alert")).toContainText("Choose at least one section");
  await expect(page.getByLabel("Comment for the organiser")).toHaveAttribute("aria-invalid", "true");

  await page.getByRole("checkbox", { name: "Attendance" }).check();
  await page.getByRole("checkbox", { name: "Room layout" }).check();
  await page.getByLabel("Comment for the organiser").fill("Is 40 the final headcount, and which layout do you need?");
  await page.getByRole("button", { name: "Send clarification request" }).click();

  await expect(page.getByRole("heading", { level: 2, name: "Clarification request sent" })).toBeVisible();
  await expect(page.getByText("awaiting clarification")).toBeVisible();
  await expect(page.getByRole("list", { name: "Sections sent" })).toContainText("Attendance");
  await expect(page.getByRole("list", { name: "Sections sent" })).toContainText("Room layout");

  // The organiser now sees the new status on their request, opens it and answers (SCRUM-78).
  await page.getByLabel("Acting as").selectOption("organiser");
  await expect(page.getByRole("heading", { name: "My event requests" })).toBeVisible();
  const organiserRow = page.getByRole("button", { name: new RegExp(eventName) });
  await expect(organiserRow).toContainText("awaiting clarification");
  await organiserRow.click();
  await expect(page.getByRole("heading", { name: "Clarification requested" })).toBeVisible();
  await expect(page.getByText("Is 40 the final headcount, and which layout do you need?")).toBeVisible();
  await expect(page.getByRole("list", { name: "Sections in question" })).toContainText("Attendance");

  await page.getByRole("button", { name: "Send response" }).click();
  await expect(page.getByRole("alert")).toContainText("Write a response");
  await expect(page.getByLabel("Your response")).toHaveAttribute("aria-invalid", "true");

  await page.getByLabel("Your response").fill("Yes, 40 including speakers, in rows facing the stage.");
  await page.getByRole("button", { name: "Send response" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Response sent" })).toBeVisible();
  await expect(page.getByText("under review")).toBeVisible();

  // Back with the coordinator, the request is under review again (8c AC 2).
  await page.getByLabel("Acting as").selectOption("coordinator");
  await expect(page.getByRole("button", { name: new RegExp(eventName) })).toContainText("under review");
});
