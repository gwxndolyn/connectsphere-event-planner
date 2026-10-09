import { expect, type Page, test } from "@playwright/test";

// Runs as the seeded attendee Calvin (VITE_DEV_ATTENDEE_ID), who the seed confirms for Tech Talk.
// He has no other open event to register for, so the test withdraws that seat, registers again,
// and withdraws once more. A local rerun needs a reseed first, since Calvin no longer holds the
// seat; the seed withdraws any leftover active rows for its pairs, so that's safe after any run.
const TECH_TALK = "Tech Talk: Agile at Scale";

async function withdrawFromTechTalk(page: Page) {
  const row = page.getByRole("listitem").filter({ hasText: TECH_TALK });
  await row.getByRole("button", { name: "Cancel registration" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Withdraw from this event?" })).toBeVisible();
  await dialog.getByRole("button", { name: "Withdraw" }).click();
  await expect(dialog.getByRole("heading", { name: "Withdrawal confirmed" })).toBeVisible();
  await expect(dialog.getByText(/Withdrawn at/)).toBeVisible();
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: TECH_TALK })).toHaveCount(0);
}

test("attendee lists events, registers, sees it in My events and withdraws", async ({ page }) => {
  const header = page.getByRole("banner");

  // The board lists the open events from the API, with Calvin's own seat and the full event.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Events at ConnectSphere" })).toBeVisible();
  const techTalkCard = page.getByRole("button", { name: new RegExp(TECH_TALK) });
  await expect(techTalkCard).toContainText("You're registered");
  // Calvin is second in the seeded queue (behind Sofia), told apart from a confirmed seat by event_id.
  const bootcampCard = page.getByRole("button", { name: /Design Sprint Bootcamp/ });
  await expect(bootcampCard).toContainText("Full");
  await expect(bootcampCard).toContainText("You're on the waitlist (#2)");
  await bootcampCard.click();
  await expect(page.getByRole("dialog")).toContainText("You're on the waitlist for this event. Find it under My events.");
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();

  // Free up the seat the seed gave him.
  await header.getByRole("button", { name: "My events" }).click();
  await expect(page.getByRole("heading", { name: "My events" })).toBeVisible();
  await withdrawFromTechTalk(page);

  // Register for it and see the confirmation.
  await header.getByRole("button", { name: "Browse events" }).click();
  await expect(techTalkCard).toContainText(/\d+ seats left/);
  await techTalkCard.click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Reserve my seat" }).click();
  await expect(dialog.getByRole("heading", { name: "You're going!" })).toBeVisible();
  await expect(dialog.getByText(TECH_TALK)).toBeVisible();
  await expect(dialog.getByText("SMU SCIS Building")).toBeVisible();
  await expect(dialog.locator(".ticket__code")).toHaveText(/^[0-9A-F]{8}$/);
  await dialog.getByRole("button", { name: "Back to events" }).click();
  await expect(techTalkCard).toContainText("You're registered");

  // It shows under Confirmed in My events, then he withdraws.
  await header.getByRole("button", { name: "My events" }).click();
  const confirmed = page.locator(".my-events__section").filter({ has: page.getByRole("heading", { name: "Confirmed" }) });
  await expect(confirmed.getByRole("listitem").filter({ hasText: TECH_TALK })).toContainText("SMU SCIS Building");
  await withdrawFromTechTalk(page);
});
