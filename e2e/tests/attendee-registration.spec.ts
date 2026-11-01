import { type APIRequestContext, expect, type Page, test } from "@playwright/test";

// Runs as the seeded attendee Calvin (VITE_DEV_ATTENDEE_ID), who the seed confirms for Tech Talk.
// He has no other open event to register for, so the test withdraws that seat, registers again,
// and withdraws once more. A local rerun needs a reseed first, since Calvin no longer holds the
// seat; the seed withdraws any leftover active rows for its pairs, so that's safe after any run.
const TECH_TALK = "Tech Talk: Agile at Scale";
const BOOTCAMP = "Design Sprint Bootcamp";
// Seeded attendees on the Bootcamp (deterministic ids from app.seed): Mei holds a seat, Sofia is
// first in the queue. The US6b test moves them through the API so Calvin gets the offer.
const MEI_ID = "435d97da-c100-5efe-90e1-56fb6c514897";
const SOFIA_ID = "1d5ff6e2-8378-55e2-acdf-838c152ddd20";
const API_URL = process.env.E2E_API_URL || "http://localhost:8000";

// All three tests act as Calvin, and each leaves the Bootcamp in the state the next one expects,
// so they run one after the other. The last (US6b) gives Calvin a Bootcamp seat, so a local rerun
// needs a reseed first.
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
  // US24 (D70): attendees see the event's approved primary venue, which the seed books for Tech Talk.
  await expect(dialog.getByText("SCIS Seminar Room 2-1")).toBeVisible();
  await expect(dialog.locator(".ticket__code")).toHaveText(/^[0-9A-F]{8}$/);
  await dialog.getByRole("button", { name: "Back to events" }).click();
  await expect(techTalkCard).toContainText("You're registered");

  // It shows under Confirmed in My events, then he withdraws.
  await header.getByRole("button", { name: "My events" }).click();
  const confirmed = page.locator(".my-events__section").filter({ has: page.getByRole("heading", { name: "Confirmed" }) });
  const row = confirmed.getByRole("listitem").filter({ hasText: TECH_TALK });
  await expect(row).toContainText("SCIS Seminar Room 2-1");
  // The primary venue's location is the in-person joining information.
  await expect(row).toContainText("School of Computing and Information Systems, Level 2");
  await withdrawFromTechTalk(page);
});

// US6a (SCRUM-52). Design Sprint Bootcamp is the seed's only full event with a waitlist, and Calvin
// is already on it (#2, behind Sofia). He leaves, then rejoins from the board with one click, as
// himself (SCRUM-136: no email is typed), which puts him back at #2. The run ends as it started, so it can rerun without a reseed; a reseed
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

  // The full event with a waitlist offers it (AC 1), with nothing to type (SCRUM-136).
  await header.getByRole("button", { name: "Browse events" }).click();
  await expect(bootcampCard).toContainText("Full · waitlist open");
  await bootcampCard.click();
  await expect(dialog).toContainText("This event is full. Join the waitlist");
  await expect(dialog.getByRole("button", { name: "Reserve my seat" })).toHaveCount(0);
  await expect(dialog.getByRole("textbox")).toHaveCount(0);

  // Joining confirms the position (AC 3).
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

  // The place shows under My events: it's his, so the next test can accept an offer for it.
  await header.getByRole("button", { name: "My events" }).click();
  await expect(waitlistedRow).toContainText("Position 2 on the waitlist");
});

/** Withdraws one of `attendeeId`'s registrations through the API, found by event name and section. */
async function withdrawAs(
  request: APIRequestContext,
  attendeeId: string,
  section: "confirmed" | "waitlisted",
  eventName: string,
) {
  const headers = { "X-Attendee-Id": attendeeId };
  const mine = await request.get(`${API_URL}/api/v1/me/registrations`, { headers });
  expect(mine.ok()).toBe(true);
  const rows: { registration_id: string; event_name: string }[] = (await mine.json())[section];
  const row = rows.find((candidate) => candidate.event_name === eventName);
  expect(row, `${eventName} under ${section}`).toBeDefined();
  const withdrawn = await request.post(`${API_URL}/api/v1/registrations/${row!.registration_id}/withdraw`, { headers });
  expect(withdrawn.ok()).toBe(true);
}

// US6b (SCRUM-76). Sofia leaves the queue, so Calvin is next; then Mei withdraws from the full
// Bootcamp, so her seat is offered to him (AC 1). He sees it under My events and accepts (AC 2).
test("attendee is offered a freed place and accepts it", async ({ page, request }) => {
  const header = page.getByRole("banner");
  await withdrawAs(request, SOFIA_ID, "waitlisted", BOOTCAMP);
  await withdrawAs(request, MEI_ID, "confirmed", BOOTCAMP);

  await page.goto("/");
  await header.getByRole("button", { name: "My events" }).click();
  const offeredSection = page
    .locator(".my-events__section")
    .filter({ has: page.getByRole("heading", { name: "Place available" }) });
  const offeredRow = offeredSection.getByRole("listitem").filter({ hasText: BOOTCAMP });
  await expect(offeredRow).toContainText("A seat opened up for you. Held until");
  // It's an offer now, not a queue position.
  await expect(
    page
      .locator(".my-events__section")
      .filter({ has: page.getByRole("heading", { name: "Waitlisted" }) })
      .getByRole("listitem")
      .filter({ hasText: BOOTCAMP }),
  ).toHaveCount(0);

  await offeredRow.getByRole("button", { name: "Accept place" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Take your place?" })).toBeVisible();
  await dialog.getByRole("button", { name: "Accept place" }).click();
  await expect(dialog.getByRole("heading", { name: "You're going!" })).toBeVisible();
  await expect(dialog.getByText(BOOTCAMP)).toBeVisible();
  await expect(dialog.locator(".ticket__code")).toHaveText(/^[0-9A-F]{8}$/);
  await dialog.getByRole("button", { name: "Done" }).click();

  // The place is his: it's under Confirmed and the offer is gone.
  await expect(offeredSection).toHaveCount(0);
  const confirmed = page.locator(".my-events__section").filter({ has: page.getByRole("heading", { name: "Confirmed" }) });
  await expect(confirmed.getByRole("listitem").filter({ hasText: BOOTCAMP })).toBeVisible();
});
