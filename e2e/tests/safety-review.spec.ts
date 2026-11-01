import { expect, test } from "@playwright/test";

// SCRUM-99 (US30a): the seeded Safety officer rejects the seeded "Safety Review Demo" (app.seed
// SAFETY_REVIEW_EVENT: an approved event with an approved booking and no safety review), the coordinator
// (Casey Tan, the dev coordinator) reads why and sends it back, the Safety officer approves it, and Casey
// confirms it. Nothing else touches the demo; rerunning on the same database needs a reseed
// (`python -m app.seed`), which puts it back in the queue.
// SCRUM-100 (US30b): between the send-back and the approval the Safety officer requests changes to the
// layout and venue, and the coordinator marks them done. One test, because the demo is shared and the
// specs run in parallel.
const EVENT = "Safety Review Demo";

test("TC-US30A-41, TC-US30B-30: reject, send back, request changes, mark them done, approve, then confirm", async ({ page }) => {
  // The seven checklist items are the groups of radios; the areas affected are a group of checkboxes.
  const checklist = () => page.getByRole("group").filter({ has: page.getByRole("radio") }).all();
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("safety_officer");
  await page.getByRole("banner").getByRole("button", { name: "Safety reviews" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await expect(page.getByRole("heading", { name: "Safety review", exact: true })).toBeVisible();

  for (const group of await checklist()) await group.getByRole("radio", { name: "Satisfactory" }).check();
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
  for (const group of await checklist()) await group.getByRole("radio", { name: "Satisfactory" }).check();

  // US30b AC 1, 2: ask for changes instead, with comments and the areas affected.
  await page.getByRole("group", { name: "Room layout" }).getByRole("radio", { name: "Issue" }).check();
  await page.getByRole("group", { name: /Areas affected/ }).getByRole("checkbox", { name: "Venue" }).check();
  await page.getByRole("group", { name: /Areas affected/ }).getByRole("checkbox", { name: "Layout" }).check();
  await page.getByLabel("Comments for the coordinator and organiser").fill("Move the stage back and widen the aisles.");
  await page.getByRole("button", { name: "Request changes" }).click();
  await expect(page.getByRole("heading", { name: "Changes requested" })).toBeVisible();

  // US30b AC 2, 3: the coordinator sees the areas and comments, nothing is reset, and Confirm stays disabled.
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  const changes = page.getByRole("region", { name: "Safety review" });
  await expect(changes).toContainText("Changes requested");
  await expect(changes.getByRole("list", { name: "Areas to review" })).toContainText("Venue");
  await expect(changes.getByRole("list", { name: "Areas to review" })).toContainText("Layout");
  await expect(changes).toContainText("Move the stage back and widen the aisles.");
  await expect(page.getByRole("list", { name: "Readiness" })).toContainText("Li Ka Shing Library Seminar Room 3-4");
  await expect(page.getByRole("button", { name: "Confirm event" })).toBeDisabled();

  // US30b AC 4: marking the changes done brings it back to the Safety officer's queue, to review again.
  await changes.getByRole("button", { name: "Mark changes done" }).click();
  await expect(changes).toContainText("Sent for another safety review.");
  await page.getByLabel("Acting as").selectOption("safety_officer");
  await page.getByRole("banner").getByRole("button", { name: "Safety reviews" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await expect(page.getByRole("region", { name: "Earlier reviews" })).toContainText("Areas to review: Venue, Layout");
  for (const group of await checklist()) await group.getByRole("radio", { name: "Satisfactory" }).check();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("heading", { name: "Safety approved" })).toBeVisible();

  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await page.getByRole("button", { name: "Confirm event" }).click();
  await expect(page.getByRole("heading", { name: "Confirmed" })).toBeVisible();
});
