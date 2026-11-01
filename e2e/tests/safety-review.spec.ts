import { expect, test } from "@playwright/test";

// SCRUM-99 (US30a): the seeded Safety officer rejects the seeded "Safety Review Demo" (app.seed
// SAFETY_REVIEW_EVENT: an approved event with an approved booking and no safety review), the coordinator
// (Casey Tan, the dev coordinator) reads why and sends it back, the Safety officer approves it, and Casey
// confirms it. Nothing else touches the demo; rerunning on the same database needs a reseed
// (`python -m app.seed`), which puts it back in the queue.
const EVENT = "Safety Review Demo";

test("TC-US30A-41: reject, send back, approve, then confirm (AC 1-4)", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("safety_officer");
  await page.getByRole("banner").getByRole("button", { name: "Safety reviews" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await expect(page.getByRole("heading", { name: "Safety review", exact: true })).toBeVisible();

  for (const group of await page.getByRole("group").all()) await group.getByRole("radio", { name: "Satisfactory" }).check();
  await page.getByRole("group", { name: "Emergency access" }).getByRole("radio", { name: "Issue" }).check();
  await page.getByLabel("Comments for the coordinator and organiser").fill("Add a second exit before the event.");
  await page.getByLabel(/^Internal notes/).fill("Check the exit plan again.");
  await page.getByRole("button", { name: "Reject safety arrangement" }).click();
  await expect(page.getByRole("heading", { name: "Safety arrangement rejected" })).toBeVisible();

  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  const outcome = page.getByRole("region", { name: "Safety review" });
  await expect(outcome).toContainText("Add a second exit before the event.");
  await expect(outcome).not.toContainText("Check the exit plan again.");
  await expect(page.getByRole("button", { name: "Confirm event" })).toBeDisabled();
  await outcome.getByRole("button", { name: "Send for another review" }).click();
  await expect(outcome).toContainText("Sent for another safety review.");

  await page.getByLabel("Acting as").selectOption("safety_officer");
  await page.getByRole("banner").getByRole("button", { name: "Safety reviews" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  // It was reviewed before, so the earlier review shows, with the internal notes only the Safety officer sees.
  await expect(page.getByRole("region", { name: "Earlier reviews" })).toContainText("Check the exit plan again.");
  for (const group of await page.getByRole("group").all()) await group.getByRole("radio", { name: "Satisfactory" }).check();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("heading", { name: "Safety approved" })).toBeVisible();

  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await page.getByRole("button", { name: "Confirm event" }).click();
  await expect(page.getByRole("heading", { name: "Confirmed" })).toBeVisible();
});
