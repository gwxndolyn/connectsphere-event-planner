import { expect, type Page, test } from "@playwright/test";

// US21 venue availability calendar (SCRUM-88, PR 2 SCRUM-123). Read-only: it books nothing. It reads
// US2's seeded slot, five days ahead (Singapore's day, as app.seed computes it): SCIS Seminar Room
// 2-1 (15 min setup, 15 min turnaround) has the requested "Analytics Club Workshop" booking 10:00–12:00,
// so it occupies 09:45–12:15; SMU Connexion Studio 3-2 is blocked 08:00–18:00 for AV maintenance.
// venue-buffers.spec.ts may add and withdraw its own booking on that day, so items are found by name,
// never by count. Analytics Club Workshop isn't the dev coordinator's event.
const SINGAPORE_DATE = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  timeZone: "Asia/Singapore",
});
const DAY = 24 * 60 * 60 * 1000;
const SEEDED_BOOKING = "Booking (requested): Analytics Club Workshop, 10:00 AM – 12:00 PM, occupied 9:45 AM – 12:15 PM";

/** Today in Singapore, as YYYY-MM-DD. */
function singaporeToday(): string {
  return new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

function plusDays(day: string, days: number): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + days * DAY).toISOString().slice(0, 10);
}

/** The seeded day, and whether it falls in next week rather than this one (weeks start on Monday). */
function seededDay(): { day: string; nextWeek: boolean } {
  const today = singaporeToday();
  const sunday = plusDays(today, 6 - ((new Date(`${today}T00:00:00Z`).getUTCDay() + 6) % 7));
  const day = plusDays(today, 5);
  return { day, nextWeek: day > sunday };
}

/** A day as the calendar names it, e.g. "Tue, Nov 3". */
function shownDay(day: string): string {
  return SINGAPORE_DATE.format(new Date(`${day}T12:00:00+08:00`));
}

async function openCalendar(page: Page, role: string, venue: string) {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption(role);
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  const calendar = page.getByRole("region", { name: "Availability calendar" });
  await calendar.getByLabel("Venue").selectOption({ label: venue });
  const { day, nextWeek } = seededDay();
  if (nextWeek) await calendar.getByRole("button", { name: "Next" }).click();
  return calendar.getByRole("group", { name: shownDay(day) });
}

test("TC-US21-23: Venue staff see the seeded booking and block, labelled, and the booking's details with its reference (AC 1 to 3)", async ({
  page,
}) => {
  const scis = await openCalendar(page, "venue_staff", "SCIS Seminar Room 2-1");
  const item = scis.getByRole("button", { name: SEEDED_BOOKING });
  await expect(item).toContainText("Setup 15 min");
  await expect(item).toContainText("Turnaround 15 min");

  await item.click();
  const dialog = page.getByRole("dialog", { name: "Booking (requested)" });
  await expect(dialog).toContainText("Analytics Club Workshop");
  await expect(dialog).toContainText("Event statusapproved");
  await expect(dialog).toContainText("Booking statusRequested");
  await expect(dialog).toContainText(/ReferenceVB-\d{4}-\d{6}/);
  await dialog.getByRole("button", { name: "Close" }).click();

  const calendar = page.getByRole("region", { name: "Availability calendar" });
  await calendar.getByLabel("Venue").selectOption({ label: "SMU Connexion Studio 3-2" });
  const connexion = calendar.getByRole("group", { name: shownDay(seededDay().day) });
  await expect(connexion.getByRole("button", { name: "Unavailable: Closed for AV maintenance, 8:00 AM – 6:00 PM" })).toBeVisible();
});

test("TC-US21-24: a coordinator sees the same booking without its reference, on an event not theirs (AC 3, D58)", async ({
  page,
}) => {
  const scis = await openCalendar(page, "coordinator", "SCIS Seminar Room 2-1");

  await scis.getByRole("button", { name: SEEDED_BOOKING }).click();
  const dialog = page.getByRole("dialog", { name: "Booking (requested)" });
  await expect(dialog).toContainText("Analytics Club Workshop");
  await expect(dialog).toContainText("Booking statusRequested");
  await expect(dialog).not.toContainText("Reference");
  await expect(dialog).not.toContainText("VB-");
});
