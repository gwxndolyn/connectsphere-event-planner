import { expect, type Page, test } from "@playwright/test";

// US23a (SCRUM-90): the coordinator requests a venue for the seeded Approved event "Venue Unavailability Demo"
// (app.seed UNAVAILABILITY_EVENT), which only this spec uses; Venue staff mark that venue unavailable over the
// request, and the coordinator sees it needs rearrangement, then withdraws it. The day is 800 to 1100 days ahead
// and changes from run to run, beyond venue-booking.spec.ts's (60 to 360) and venue-hold.spec.ts's (400 to 700), so
// the period never meets their rows. A reseed deletes the event's bookings and the periods that marked them.
const EVENT = "Venue Unavailability Demo";
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

async function openEvent(page: Page) {
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  return page.getByRole("region", { name: "Venue bookings" });
}

test("TC-US23A-20: Venue staff mark a booked venue unavailable; the coordinator sees it needs rearrangement (AC 1, 3, 4, 5)", async ({
  page,
}) => {
  const day = singaporeDay(800 + (Math.floor(Date.now() / 1000) % 300));
  const shown = `${VENUE}, ${SINGAPORE_DATE.format(new Date(`${day}T12:00:00+08:00`))}, 3:00 PM – 4:00 PM`;
  await page.goto("/");

  // The coordinator requests the venue.
  let bookings = await openEvent(page);
  await bookings.getByRole("button", { name: "Request venue" }).click();
  await page.getByLabel("Venue", { exact: true }).selectOption({ label: `${VENUE} (capacity 60)` });
  await page.getByLabel("Purpose").fill("Main hall");
  await page.getByLabel("Date").fill(day);
  await page.getByLabel("Start time").fill("15:00");
  await page.getByLabel("End time").fill("16:00");
  await page.getByLabel("Allocated attendees").fill("30");
  await page.getByLabel("Layout", { exact: true }).selectOption("theatre");
  await page.getByRole("button", { name: "Send request" }).click();
  const row = bookings.getByRole("listitem", { name: shown });
  await expect(row).toContainText("Requested");

  // AC 1, 3: Venue staff mark the venue unavailable over it, for a reason, and see it needs rearranging.
  await page.getByLabel("Acting as").selectOption("venue_staff");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  const panel = page.getByRole("region", { name: "Mark a venue unavailable" });
  await panel.getByRole("button", { name: "Mark unavailable" }).click();
  await panel.getByLabel("Venue").selectOption({ label: VENUE });
  await panel.getByLabel("Start date").fill(day);
  await panel.getByLabel("Start time").fill("13:00");
  await panel.getByLabel("End date").fill(day);
  await panel.getByLabel("End time").fill("17:00");
  await panel.getByLabel("Reason").selectOption("maintenance");
  await panel.getByLabel("Note (optional)").fill("Air-conditioning repair");
  await panel.getByRole("button", { name: "Mark unavailable" }).click();
  const status = panel.getByRole("status");
  await expect(status).toContainText(`${VENUE} is unavailable from`);
  await expect(status).toContainText("(Maintenance)");
  await expect(status.getByRole("list", { name: "Bookings needing rearrangement" })).toContainText(EVENT);

  // AC 3, 4: the coordinator sees it needs rearrangement, with the period and reason; the booking is kept.
  bookings = await openEvent(page);
  await expect(row).toContainText("Needs rearrangement");
  await expect(row).toContainText("(Maintenance): Air-conditioning repair");
  await expect(row).toContainText("Requested");

  // Leave the event without a live booking for the next run.
  await row.getByRole("button", { name: "Withdraw" }).click();
  await page.getByRole("dialog", { name: "Withdraw this venue request?" }).getByRole("button", { name: "Withdraw request" }).click();
  await expect(row).toContainText("Withdrawn");
});
