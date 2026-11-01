import { expect, test } from "@playwright/test";

// US9 (SCRUM-12): the seeded Cancellation Demo, which only this spec uses and a reseed puts back in Planning
// (`python -m app.seed`; CI seeds fresh). One journey, since each step needs the one before.
test("TC-US9-32: the organiser asks to cancel, the coordinator rejects, then cancels; both see the record (AC 1 to 4, 8)", async ({ page }) => {
  await page.goto("/");

  // AC 1: the organiser asks, with a reason.
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: /Cancellation Demo/ }).click();
  const organiserPanel = page.getByRole("region", { name: "Cancellation" });
  await organiserPanel.getByRole("button", { name: "Request cancellation" }).click();
  await organiserPanel.getByLabel("Reason for cancelling").fill("The speaker has withdrawn.");
  await organiserPanel.getByRole("button", { name: "Send cancellation request" }).click();
  await expect(organiserPanel.getByRole("status")).toContainText("Cancellation request sent.");
  await expect(organiserPanel.getByRole("list", { name: "Cancellation history" })).toContainText("Waiting for decision");

  // AC 2: the assigned coordinator rejects it, with a reason; the event goes ahead.
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: /Cancellation Demo/ }).click();
  const coordinatorPanel = page.getByRole("region", { name: "Cancellation" });
  await expect(coordinatorPanel).toContainText("asked to cancel this event: The speaker has withdrawn.");
  await coordinatorPanel.getByRole("button", { name: "Reject cancellation" }).click();
  await coordinatorPanel.getByLabel("Reason for rejecting").fill("A replacement speaker is confirmed.");
  await coordinatorPanel.getByRole("button", { name: "Reject cancellation" }).click();
  await expect(coordinatorPanel.getByRole("status")).toContainText("Cancellation request rejected.");

  // AC 3, 4: the coordinator then cancels it directly, after confirming it can't be undone.
  await coordinatorPanel.getByRole("button", { name: "Cancel event" }).click();
  await coordinatorPanel.getByLabel("Reason for cancelling").fill("The venue is closed for repairs.");
  await coordinatorPanel.getByRole("button", { name: "Continue" }).click();
  const confirm = coordinatorPanel.getByRole("group", { name: "Confirm cancellation" });
  await expect(confirm).toContainText("This can't be undone.");
  await confirm.getByRole("button", { name: "Cancel event" }).click();
  await expect(coordinatorPanel.getByRole("status")).toContainText("The event is cancelled.");
  await expect(coordinatorPanel.getByText("This event is cancelled.")).toBeVisible();

  // AC 8: the organiser sees it cancelled, with who did it and both requests' outcomes.
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: /Cancellation Demo/ }).click();
  const record = page.getByRole("region", { name: "Cancellation" });
  await expect(record.getByText("This event is cancelled.")).toBeVisible();
  const history = record.getByRole("list", { name: "Cancellation history" });
  await expect(history).toContainText("Cancelled by Casey Tan");
  await expect(history).toContainText("Why it was rejected: A replacement speaker is confirmed.");
  await expect(record.getByRole("button", { name: "Request cancellation" })).toHaveCount(0);
});
