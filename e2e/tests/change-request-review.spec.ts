import { expect, test, type Page } from "@playwright/test";

// US29b (SCRUM-143): the organiser asks for a change to the seeded "Change Request Demo" (app.seed
// CHANGE_REQUEST_EVENT: Confirmed, safety-approved, an approved booking and a reserved projector), the coordinator
// approves it, and both see the outcome. The demo is seeded with a pending request to start an hour later; this
// asks for attendance and equipment instead, fields that request doesn't touch, so it stays pending and not stale.
// No other spec touches the demo. Approving moves it back to Planning for good, so rerunning on the same database
// needs a reseed (`python -m app.seed`), which puts it back.
const EVENT = "Change Request Demo";
const REASON = `A second cohort joins, with its own projector (${Date.now().toString(36)})`;

test.describe.configure({ mode: "serial" });

async function openAs(page: Page, role: "organiser" | "coordinator") {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption(role);
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
}

test("TC-US29B-33: the organiser asks, the coordinator approves, both see the outcome (AC 1-6)", async ({ page }) => {
  // The organiser asks for more attendees and a second projector.
  await openAs(page, "organiser");
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  const panel = page.getByRole("region", { name: "Change requests" });
  await panel.getByRole("button", { name: "Request a change" }).click();
  await page.getByLabel("Expected attendees").fill("30");
  await page.getByLabel("Equipment needs").fill("Two projectors");
  await page.getByLabel("Reason for the change").fill(REASON);
  await page.getByRole("button", { name: "Review change" }).click();
  await page.getByRole("button", { name: "Send change request" }).click();
  await expect(page.getByRole("status")).toContainText("Change request sent.");

  // The coordinator finds it waiting, opens it and sees what approving does.
  await openAs(page, "coordinator");
  const queue = page.getByRole("region", { name: /Change requests to review/ });
  await queue.getByRole("listitem", { name: new RegExp(EVENT) }).filter({ hasText: "Significant" }).first().getByRole("button", { name: "Review" }).click();
  const review = page.getByRole("region", { name: "Change requests for this event" });
  const ours = review.getByRole("article").filter({ hasText: REASON });
  const changes = ours.getByRole("table", { name: "Requested changes" });
  await expect(changes.getByRole("row", { name: /Expected attendees/ })).toContainText("2030");
  await expect(changes.getByRole("row", { name: /Equipment needs/ })).toContainText("Two projectors");
  const notice = ours.getByRole("note", { name: "What approving does" });
  await expect(notice).toContainText("moves this event back to Planning");
  await expect(notice).toContainText("needs a new safety review");

  await ours.getByRole("button", { name: "Approve" }).click();
  await ours.getByRole("button", { name: "Approve change" }).click();
  await expect(review.getByRole("status")).toContainText("Approved. The event is now Planning.");

  // Back in Planning: the booking and the projector to review, and a new safety review needed.
  const flags = page.getByRole("region", { name: "Review after change" });
  await expect(flags.getByRole("listitem")).toHaveCount(2);
  await expect(flags.getByRole("listitem").filter({ hasText: "Li Ka Shing Library Seminar Room 3-4" })).toBeVisible();
  await expect(flags.getByRole("listitem").filter({ hasText: "Projector × 1" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Safety review" })).toContainText("A new safety review is needed.");
  await expect(page.getByRole("button", { name: "Confirm event" })).toBeDisabled();
  // The seeded start-and-end request is still waiting, and still applies as asked.
  const seeded = review.getByRole("article").filter({ hasText: "flight now lands later" });
  await expect(seeded).toBeVisible();
  await expect(seeded).not.toContainText("Changed since requested");

  // The organiser sees it approved.
  await openAs(page, "organiser");
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  const mine = page.getByRole("list", { name: "Your change requests" }).getByRole("listitem").filter({ hasText: REASON });
  await expect(mine).toContainText("Approved");
  await expect(mine).toContainText("Decided");
});
