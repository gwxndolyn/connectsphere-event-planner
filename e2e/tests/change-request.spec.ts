import { expect, test } from "@playwright/test";

// US29a (SCRUM-97): the organiser submits their own uniquely named request, then asks for a change to it, so no
// seeded row is touched and a rerun needs no reseed.
test("TC-US29A-24: the organiser requests a change, checks it, gives a reason, and sees it Pending (AC 1 to 4, 6)", async ({ page }) => {
  const name = `Change request workshop ${Date.now().toString(36)}`;
  const preferredDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: "Create request" }).click();
  await page.getByLabel("Event name").fill(name);
  await page.getByLabel("Event category").fill("Workshop");
  await page.getByLabel("Purpose / description").fill("Try requesting a change");
  await page.getByLabel("Preferred date").fill(preferredDate);
  await page.getByLabel("Preferred start time").fill("09:30");
  await page.getByLabel("Preferred end time").fill("11:30");
  await page.getByLabel("Expected attendees").fill("30");
  await page.getByRole("button", { name: "Submit request" }).click();
  await expect(page.getByRole("heading", { level: 2, name: "Submission confirmed" })).toBeVisible();

  const panel = page.getByRole("region", { name: "Change requests" });
  await panel.getByRole("button", { name: "Request a change" }).click();
  await page.getByLabel("Expected attendees").fill("45");
  await page.getByLabel("Preferred end time").fill("12:00");
  await page.getByRole("button", { name: "Review change" }).click();
  await expect(page.getByRole("alert")).toContainText("Give a reason for the change.");

  await page.getByLabel("Reason for the change").fill("A second cohort is joining.");
  await page.getByRole("button", { name: "Review change" }).click();
  const preview = page.getByRole("table", { name: "Changes to send" });
  await expect(preview.getByRole("row", { name: /Expected attendees/ })).toContainText("3045");
  await expect(preview.getByRole("row", { name: /Preferred end time/ })).toContainText("11:3012:00");
  await page.getByRole("button", { name: "Send change request" }).click();

  await expect(page.getByRole("status")).toContainText("Change request sent.");
  const list = panel.getByRole("list", { name: "Your change requests" });
  await expect(list).toContainText("Pending");
  await expect(list).toContainText("Reason: A second cohort is joining.");

  // AC 4: the request itself is unchanged; reopening shows the change still pending.
  await page.getByRole("button", { name: "Back to my requests" }).first().click();
  await page.getByRole("button", { name: new RegExp(name) }).click();
  await expect(panel.getByRole("list", { name: "Your change requests" })).toContainText("Pending");
});
