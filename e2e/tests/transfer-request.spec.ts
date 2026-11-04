import { expect, test } from "@playwright/test";

// US10e AC 6 (SCRUM-146): the seeded coordinator asks the Leads to transfer Event Planning Demo (planning, theirs).
// Nothing on the event changes, so this can share it with event-edit.spec.ts; only a notification is added, found
// by a reason unique to this run.
test("TC-US10E-34: the coordinator requests a transfer and the Coordinator Lead is told (AC 6)", async ({ page }) => {
  const reason = `On leave that week (${Date.now()})`;

  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Events", exact: true }).click();
  await page.getByRole("button", { name: /Event Planning Demo/ }).click();
  const transfer = page.getByRole("region", { name: "Transfer" });
  await transfer.getByRole("button", { name: "Request a transfer" }).click();
  await transfer.getByLabel("Reason for the transfer").fill(reason);
  await transfer.getByRole("button", { name: "Send" }).click();
  await expect(transfer.getByRole("status")).toHaveText("Transfer requested. The Coordinator Leads have been told.");

  await page.getByLabel("Acting as").selectOption("coordinator_lead");
  await page.getByRole("banner").getByRole("button", { name: /^Notifications/ }).click();
  const entry = page.getByRole("list", { name: "Notifications" }).getByRole("listitem").filter({ hasText: reason });
  await expect(entry).toContainText("asked to transfer request");
  await expect(entry).toContainText("Unread");
});
