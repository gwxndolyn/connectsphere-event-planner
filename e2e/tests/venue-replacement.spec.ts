import { expect, type Page, test } from "@playwright/test";

// US23b (SCRUM-91): the coordinator requests a venue for the seeded Approved event "Replacement Venue Demo"
// (app.seed REPLACEMENT_EVENT), which only this spec uses; Venue staff approve it and then mark it unavailable; the
// coordinator finds a replacement from the notice, Venue staff approve that, and the original reads Replaced. The day
// is 1100 to 1400 days ahead and changes from run to run, beyond venue-unavailability.spec.ts's (800 to 1100), so
// the period never meets its rows. A reseed deletes the event's bookings and the periods that marked them.
const EVENT = "Replacement Venue Demo";
const ORIGINAL = "Li Ka Shing Library Seminar Room 3-4";
const REPLACEMENT = "SCIS Seminar Room 2-1";

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

async function approvePending(page: Page, venue: string, window: string) {
  await page.getByLabel("Acting as").selectOption("venue_staff");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  const row = page
    .getByRole("list", { name: "Pending venue requests" })
    .getByRole("listitem", { name: `${EVENT} at ${venue}` })
    .filter({ hasText: window });
  await row.getByRole("button", { name: "Approve" }).click();
  await expect(row).toHaveCount(0);
}

test("TC-US23B-20: the coordinator replaces a venue that became unavailable; the original reads Replaced (AC 1 to 4)", async ({
  page,
}) => {
  const day = singaporeDay(1100 + (Math.floor(Date.now() / 1000) % 300));
  const date = SINGAPORE_DATE.format(new Date(`${day}T12:00:00+08:00`));
  const window = `${date}, 3:00 PM – 4:00 PM`;
  await page.goto("/");

  // The coordinator requests the venue, and Venue staff approve it.
  let bookings = await openEvent(page);
  await bookings.getByRole("button", { name: "Request venue" }).click();
  await page.getByLabel("Venue", { exact: true }).selectOption({ label: `${ORIGINAL} (capacity 60)` });
  await page.getByLabel("Purpose").fill("Main hall");
  await page.getByLabel("Date").fill(day);
  await page.getByLabel("Start time").fill("15:00");
  await page.getByLabel("End time").fill("16:00");
  await page.getByLabel("Allocated attendees").fill("30");
  await page.getByLabel("Layout", { exact: true }).selectOption("theatre");
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(bookings.getByRole("listitem", { name: `${ORIGINAL}, ${window}` })).toContainText("Requested");
  await approvePending(page, ORIGINAL, window);

  // Venue staff mark it unavailable over the booking.
  const panel = page.getByRole("region", { name: "Mark a venue unavailable" });
  await panel.getByRole("button", { name: "Mark unavailable" }).click();
  await panel.getByLabel("Venue").selectOption({ label: ORIGINAL });
  await panel.getByLabel("Start date").fill(day);
  await panel.getByLabel("Start time").fill("13:00");
  await panel.getByLabel("End date").fill(day);
  await panel.getByLabel("End time").fill("17:00");
  await panel.getByLabel("Reason").selectOption("safety");
  await panel.getByLabel("Note (optional)").fill("Ceiling inspection");
  await panel.getByRole("button", { name: "Mark unavailable" }).click();
  await expect(panel.getByRole("list", { name: "Bookings needing rearrangement" })).toContainText(EVENT);

  // AC 1, 2: the coordinator sees the notice and searches from it with the booking's time and attendance.
  bookings = await openEvent(page);
  const original = bookings.getByRole("listitem", { name: `${ORIGINAL}, ${window}` });
  await expect(original).toContainText("Needs rearrangement");
  await expect(original).toContainText("(Safety): Ceiling inspection");
  await original.getByRole("button", { name: "Find a replacement" }).click();
  await expect(page.getByRole("heading", { name: "Find a replacement venue" })).toBeVisible();
  await expect(page.getByText(new RegExp(`free ${date}, 3:00 PM – 4:00 PM for 30 attendees`))).toBeVisible();
  // AC 3: requested from the results, for Venue staff to approve like any request.
  await page.getByLabel("Venue", { exact: true }).selectOption({ label: `${REPLACEMENT} (capacity 40)` });
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByText(new RegExp(`Replacement requested: ${REPLACEMENT}`)).first()).toBeVisible();
  await approvePending(page, REPLACEMENT, window);

  // AC 4: the original reads Replaced, keeping its details; the replacement is the event's venue.
  bookings = await openEvent(page);
  await expect(original).toContainText("Replaced");
  await expect(original).toContainText(`Replaced by ${REPLACEMENT}`);
  const replacement = bookings.getByRole("listitem", { name: `${REPLACEMENT}, ${window}` });
  await expect(replacement).toContainText("Approved");
  await expect(replacement).toContainText("Primary");

  // Leave the event without a live booking for the next run.
  await replacement.getByRole("button", { name: "Withdraw" }).click();
  await page.getByRole("dialog", { name: "Withdraw this approved venue?" }).getByRole("button", { name: "Withdraw venue" }).click();
  await expect(replacement).toContainText("Withdrawn");
});
