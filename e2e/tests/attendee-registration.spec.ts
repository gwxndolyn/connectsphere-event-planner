import { expect, type Page, test } from "@playwright/test";

// Runs as the seeded attendee Calvin (VITE_DEV_ATTENDEE_ID), who the seed confirms for Tech Talk.
// He has no other open event to register for, so the test withdraws that seat, registers again,
// and withdraws once more. A local rerun needs a reseed first, since Calvin no longer holds the
// seat; the seed withdraws any leftover active rows for its pairs, so that's safe after any run.
const TECH_TALK = "Tech Talk: Agile at Scale";
const BOOTCAMP = "Design Sprint Bootcamp";
const CALVIN_EMAIL = "calvin.ng.2024@smu.edu.sg";

// Both tests act as Calvin, and the second briefly takes him off the Bootcamp waitlist that the
// first one checks, so they run one after the other.
test.describe.configure({ mode: "serial" });

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

// US6a (SCRUM-52). Design Sprint Bootcamp is the seed's only full event with a waitlist, and Calvin
// is already on it (#2, behind Sofia). He leaves, then rejoins from the board with his email, which
// puts him back at #2. The run ends as it started, so it can rerun without a reseed; a reseed
// afterwards restores his seeded row and withdraws the new one.
test("attendee joins the waitlist of a full event and sees the position", async ({ page }) => {
  const header = page.getByRole("banner");
  const bootcampCard = page.getByRole("button", { name: new RegExp(BOOTCAMP) });
  const waitlistedRow = page
    .locator(".my-events__section")
    .filter({ has: page.getByRole("heading", { name: "Waitlisted" }) })
    .getByRole("listitem")
    .filter({ hasText: BOOTCAMP });

  // Take him off the waitlist first.
  await page.goto("/");
  await header.getByRole("button", { name: "My events" }).click();
  await expect(waitlistedRow).toContainText("Position 2 on the waitlist");
  await waitlistedRow.getByRole("button", { name: "Leave waitlist" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Leave waitlist" }).click();
  await expect(dialog.getByRole("heading", { name: "You've left the waitlist" })).toBeVisible();
  await dialog.getByRole("button", { name: "Done" }).click();
  await expect(waitlistedRow).toHaveCount(0);

  // The full event with a waitlist offers it (AC 1); the email is required.
  await header.getByRole("button", { name: "Browse events" }).click();
  await expect(bootcampCard).toContainText("Full · waitlist open");
  await bootcampCard.click();
  await expect(dialog).toContainText("This event is full. Join the waitlist");
  await expect(dialog.getByRole("button", { name: "Reserve my seat" })).toHaveCount(0);
  const email = dialog.getByLabel("Email");
  await dialog.getByRole("button", { name: "Join the waitlist" }).click();
  await expect.poll(() => email.evaluate((input: HTMLInputElement) => input.validity.valueMissing)).toBe(true);

  // Joining confirms the position (AC 3).
  await email.fill(CALVIN_EMAIL);
  await dialog.getByRole("button", { name: "Join the waitlist" }).click();
  await expect(dialog.getByRole("heading", { name: "You're on the waitlist" })).toBeVisible();
  await expect(dialog.locator(".ticket__code")).toHaveText("You're #2 in the queue");
  await dialog.getByRole("button", { name: "Back to events" }).click();
  await expect(bootcampCard).toContainText("You're on the waitlist (#2)");

  // An event with places left offers no waitlist (AC 2): the first test left Tech Talk open to him.
  await page.getByRole("button", { name: new RegExp(TECH_TALK) }).click();
  await expect(dialog.getByRole("button", { name: "Reserve my seat" })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Join the waitlist" })).toHaveCount(0);
  await dialog.getByRole("button", { name: "Close" }).click();

  // The place shows under My events, linked to him by the email.
  await header.getByRole("button", { name: "My events" }).click();
  await expect(waitlistedRow).toContainText("Position 2 on the waitlist");
});
