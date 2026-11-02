import { expect, test } from "@playwright/test";

// US25 (SCRUM-93): Venue staff hold a venue for the seeded Approved event "Venue Hold Demo" (app.seed HOLD_EVENT),
// which only this spec uses; the coordinator confirms the hold into a request, then withdraws it so a rerun finds
// the window free. The hold is on a day 400 to 700 days ahead that changes from run to run, beyond the 60 to 360
// days venue-booking.spec.ts books, so the two never meet at one venue. A reseed also clears the event's rows.
const EVENT = "Venue Hold Demo";
const VENUE = "Li Ka Shing Library Seminar Room 3-4";

const SINGAPORE_DATE = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  timeZone: "Asia/Singapore",
});

function singaporeDay(daysAhead: number): string {
  const singapore = new Date(Date.now() + 8 * 60 * 60 * 1000);
  singapore.setUTCDate(singapore.getUTCDate() + daysAhead);
  return singapore.toISOString().slice(0, 10);
}

test("TC-US25-24: Venue staff hold a venue, the coordinator sees and confirms it, then withdraws it (AC 1, 2, 4, 5)", async ({ page }) => {
  const day = singaporeDay(400 + (Math.floor(Date.now() / 1000) % 300));
  const expires = singaporeDay(3);
  await page.goto("/");

  // AC 1: Venue staff hold the venue until an expiry.
  await page.getByLabel("Acting as").selectOption("venue_staff");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  const holds = page.getByRole("region", { name: "Hold a venue" });
  await holds.getByRole("button", { name: "Place a hold" }).click();
  await holds.getByLabel("Event").selectOption({ label: EVENT });
  await holds.getByLabel("Venue", { exact: true }).selectOption({ label: `${VENUE} (capacity 60)` });
  await holds.getByLabel("Purpose").fill("Main hall");
  await holds.getByLabel("Date").fill(day);
  await holds.getByLabel("Start time").fill("15:00");
  await holds.getByLabel("End time").fill("16:00");
  await holds.getByLabel("Allocated attendees").fill("30");
  await holds.getByLabel("Layout").selectOption("theatre");
  await holds.getByLabel("Hold expires on").fill(expires);
  await holds.getByRole("button", { name: "Place hold" }).click();
  await expect(holds.getByRole("status")).toContainText(`Held ${VENUE} for ${EVENT} until`);

  // AC 4, 5: the coordinator sees the hold with its expiry, and confirms it into a request.
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  const bookings = page.getByRole("region", { name: "Venue bookings" });
  // By venue and window, as venue-booking.spec.ts does: an earlier run's withdrawn row has another day.
  const shown = `${VENUE}, ${SINGAPORE_DATE.format(new Date(`${day}T12:00:00+08:00`))}, 3:00 PM – 4:00 PM`;
  const row = bookings.getByRole("listitem", { name: shown });
  await expect(row).toContainText("Held for this event until");
  await row.getByRole("button", { name: "Confirm hold" }).click();
  await expect(bookings.getByRole("status")).toContainText(`Hold confirmed: ${VENUE} is now a request.`);
  await expect(row).toContainText("From a hold: Venue staff must approve it by");

  // Leave the window free for the next run.
  await row.getByRole("button", { name: "Withdraw" }).click();
  await page.getByRole("dialog", { name: "Withdraw this venue request?" }).getByRole("button", { name: "Withdraw request" }).click();
  await expect(row).toContainText("Withdrawn");
});
