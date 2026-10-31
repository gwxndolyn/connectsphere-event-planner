import { expect, type Page, test } from "@playwright/test";

// US24 several venues for one event (SCRUM-92, PR 3 SCRUM-129). Uses the seeded Multi-Venue Conference
// Demo (app.seed MULTI_VENUE_EVENT): approved, assigned to the dev coordinator, created by the dev
// organiser, preferred day twelve days ahead (Singapore's day, as the seed computes it), 09:00-17:00,
// with an approved primary main hall (preparation in progress), a requested Breakout A and a rejected
// Breakout B. Playwright runs fullyParallel, so TC-US24-27 can read the event while TC-US24-26 has its
// own Breakout C on it: rows are found by name or reference, never counted. TC-US24-26 withdraws what it
// requests, so a rerun on the same database finds the window free again.
const EVENT = "Multi-Venue Conference Demo";

function seededDay(): string {
  const singapore = new Date(Date.now() + 8 * 60 * 60 * 1000);
  singapore.setUTCDate(singapore.getUTCDate() + 12);
  return singapore.toISOString().slice(0, 10);
}

async function openEvent(page: Page, role: "coordinator" | "organiser") {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption(role);
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
}

test("TC-US24-26: the coordinator adds a breakout room, sees it pending and not arranged, and withdraws it (AC 1, 4, 7)", async ({
  page,
}) => {
  await openEvent(page, "coordinator");
  await expect(page.getByRole("heading", { name: "Review request" })).toBeVisible();
  const panel = page.getByRole("region", { name: "Venue bookings" });
  await panel.getByRole("button", { name: "Request venue" }).click();

  await page.getByLabel("Venue", { exact: true }).selectOption({ label: "SMU Connexion Studio 3-2 (capacity 30)" });
  await page.getByLabel("Purpose").fill("Breakout C");
  // D65: the event's preferred day and times are shown, and the window stays inside them.
  await expect(page.getByText(/^Event schedule: .*9:00 AM – 5:00 PM$/)).toBeVisible();
  await page.getByLabel("Date").fill(seededDay());
  await page.getByLabel("Start time").fill("10:00");
  await page.getByLabel("End time").fill("12:00");
  await page.getByLabel("Allocated attendees").fill("20");
  await page.getByLabel("Layout", { exact: true }).selectOption("classroom");
  await page.getByRole("button", { name: "Send request" }).click();

  const notice = page.getByRole("status").filter({ hasText: "Venue requested" });
  await expect(notice).toContainText(/SMU Connexion Studio 3-2, .* \(VB-\d{4}-\d{6}\)/);
  const reference = (await notice.textContent())?.match(/VB-\d{4}-\d{6}/)?.[0];
  expect(reference).toBeTruthy();
  const row = panel.getByRole("listitem").filter({ hasText: reference! });
  await expect(row).toContainText("Breakout C");
  await expect(row).toContainText("Requested");
  await expect(row).toContainText("20 attending");
  await expect(row.getByText("Primary", { exact: true })).toHaveCount(0);

  // AC 7: not every venue is approved, so the venues aren't arranged.
  const summary = panel.getByRole("region", { name: "Venue arrangements" });
  await expect(summary).toContainText("Venues not arranged");
  await expect(summary.getByRole("list", { name: "What's missing" })).toContainText("waiting for Venue staff");

  // Tidy up, so a rerun on this database can request the same window.
  await row.getByRole("button", { name: "Withdraw" }).click();
  await page.getByRole("dialog", { name: "Withdraw this venue request?" }).getByRole("button", { name: "Withdraw request" }).click();
  await expect(row).toContainText("Withdrawn");
});

test("TC-US24-27: the Organiser sees the event's venues with their status, unavailability and next action (AC 4, D71)", async ({
  page,
}) => {
  await openEvent(page, "organiser");
  const venues = page.getByRole("region", { name: "Venues" });
  const list = venues.getByRole("list", { name: "This event's venues" });

  const main = list.getByRole("listitem", { name: /^Main hall:/ });
  await expect(main).toContainText("Approved");
  await expect(main.getByText("Primary", { exact: true })).toBeVisible();
  await expect(main).toContainText("Preparation: In progress");
  await expect(main).toContainText("Next: Nothing to do");

  const breakoutA = list.getByRole("listitem", { name: /^Breakout A:/ });
  await expect(breakoutA).toContainText("Requested");
  await expect(breakoutA).toContainText("Next: Waiting for Venue staff");

  const breakoutB = list.getByRole("listitem", { name: /^Breakout B:/ });
  await expect(breakoutB).toContainText("Rejected");
  // The reason already ends in a full stop, so the sentence gets no second one.
  await expect(
    breakoutB.getByText("Venue staff rejected it: The library is closed to events that afternoon.", { exact: true }),
  ).toBeVisible();
  await expect(breakoutB).toContainText("Next: Coordinator to rebook");

  await expect(venues.getByRole("region", { name: "Venue arrangements" })).toContainText("Venues not arranged");
  // Read-only: the Organiser can't change anything here.
  await expect(venues.getByRole("button")).toHaveCount(0);
});
