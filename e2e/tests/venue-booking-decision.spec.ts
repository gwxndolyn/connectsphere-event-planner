import { expect, type Page, test } from "@playwright/test";

// US4 approve or reject a venue booking request (SCRUM-8). Like venue-booking.spec.ts, it books the
// seeded Approved event "Venue Booking Demo" and creates its own rows (docs/testing/README.md). An
// approved booking can't be withdrawn, so a rerun on the same database must not find it in the way:
// each run uses a day 400 to 20,400 days ahead that changes every second, clear of US22's 60 to 360
// days and of US2's seeded slot. Rows are found by venue and window, never by count.
const EVENT = "Venue Booking Demo";
const SINGAPORE_DATE = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  timeZone: "Asia/Singapore",
});

function runDay(): string {
  const offset = 400 + (Math.floor(Date.now() / 1000) % 20_000);
  const singapore = new Date(Date.now() + 8 * 60 * 60 * 1000);
  singapore.setUTCDate(singapore.getUTCDate() + offset);
  return singapore.toISOString().slice(0, 10);
}

/** The window as the screens show it, e.g. "Mon, Feb 1, 9:00 AM – 11:00 AM". */
function shownWindow(day: string, start: string, end: string): string {
  const time = (hhmm: string) => {
    const [hour, minute] = hhmm.split(":").map(Number);
    return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`;
  };
  return `${SINGAPORE_DATE.format(new Date(`${day}T12:00:00+08:00`))}, ${time(start)} – ${time(end)}`;
}

async function openEvent(page: Page) {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await expect(page.getByRole("heading", { name: "Review request" })).toBeVisible();
  return page.getByRole("region", { name: "Venue bookings" });
}

async function requestVenue(page: Page, venue: string, day: string, start: string, end: string, layout: string) {
  const panel = await openEvent(page);
  await panel.getByRole("button", { name: "Request venue" }).click();
  await page.getByLabel("Venue", { exact: true }).selectOption({ label: venue });
  // US24 (D66): every venue request says what the venue is for.
  await page.getByLabel("Purpose").fill("Main hall");
  await page.getByLabel("Date").fill(day);
  await page.getByLabel("Start time").fill(start);
  await page.getByLabel("End time").fill(end);
  await page.getByLabel("Allocated attendees").fill("30");
  await page.getByLabel("Layout", { exact: true }).selectOption(layout);
  await page.getByRole("button", { name: "Send request" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Venue requested" })).toBeVisible();
}

async function pendingRow(page: Page, venue: string, window: string) {
  await page.getByLabel("Acting as").selectOption("venue_staff");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  return page
    .getByRole("list", { name: "Pending venue requests" })
    .getByRole("listitem", { name: `${EVENT} at ${venue}` })
    .filter({ hasText: window });
}

function bookingRow(page: Page, venue: string, window: string) {
  return page.getByRole("region", { name: "Venue bookings" }).getByRole("listitem", { name: `${venue}, ${window}` }).last();
}

test("TC-US4-10: Venue staff approve a request; the coordinator sees it Approved (AC 1, 2, 6)", async ({ page }) => {
  const day = runDay();
  const window = shownWindow(day, "09:00", "11:00");
  await requestVenue(page, "SCIS Seminar Room 2-1 (capacity 40)", day, "09:00", "11:00", "classroom");

  const row = await pendingRow(page, "SCIS Seminar Room 2-1", window);
  await expect(row).toContainText("30 attending");
  await row.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("status")).toContainText(`Approved: SCIS Seminar Room 2-1 is reserved for ${EVENT}, ${window}.`);
  await expect(row).toHaveCount(0);

  await openEvent(page);
  await expect(bookingRow(page, "SCIS Seminar Room 2-1", window)).toContainText("Approved");
});

test("TC-US4-11: Venue staff reject with a reason and an alternative; the coordinator sees them and can request again (AC 4, 5, 8)", async ({ page }) => {
  const day = runDay();
  const window = shownWindow(day, "14:00", "16:00");
  await requestVenue(page, "Li Ka Shing Library Seminar Room 3-4 (capacity 60)", day, "14:00", "16:00", "classroom");

  const row = await pendingRow(page, "Li Ka Shing Library Seminar Room 3-4", window);
  await row.getByRole("button", { name: "Reject" }).click();
  const dialog = page.getByRole("dialog", { name: "Reject this venue request?" });
  await dialog.getByLabel("Reason (optional)").fill("Closed for an exam that afternoon");
  await dialog.getByLabel("Suggested alternative (optional)").fill("SCIS Seminar Room 2-1 is free");
  await dialog.getByRole("button", { name: "Reject request" }).click();
  await expect(page.getByRole("status")).toContainText("Rejected the request for Li Ka Shing Library Seminar Room 3-4");
  await expect(row).toHaveCount(0);

  const panel = await openEvent(page);
  const rejected = bookingRow(page, "Li Ka Shing Library Seminar Room 3-4", window);
  await expect(rejected).toContainText("Rejected");
  await expect(rejected).toContainText("Reason: Closed for an exam that afternoon");
  await expect(rejected).toContainText("Suggested instead: SCIS Seminar Room 2-1 is free");
  // The event stays bookable (AC 8): Request venue is still offered.
  await expect(panel.getByRole("button", { name: "Request venue" })).toBeVisible();
});
