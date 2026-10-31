import { expect, type Page, test } from "@playwright/test";

// US13 setup and turnaround buffers (SCRUM-16, PR 3 SCRUM-116). Books the seeded Approved event
// "Venue Booking Demo" (app.seed BOOKABLE_EVENT) like venue-booking.spec.ts. The overlap test uses
// US2's seeded slot, five days ahead (Singapore's day, as the seed computes it): SCIS Seminar Room
// 2-1 (15 min setup, 15 min turnaround) has a requested booking 10:00–12:00, so it occupies
// 09:45–12:15. A request starting 12:15 would set up from 12:00, inside that turnaround; one
// starting 12:30 sets up from 12:15, touching it. venue-search.spec.ts reads that day at 10:00–12:00
// and 17:00–17:50, which 12:30–13:30 (occupied 12:15–13:45) doesn't touch. The test withdraws what it
// booked, so a rerun on the same database finds the window free again. Rows are found by venue and
// window, never by count.
const EVENT = "Venue Booking Demo";
const SINGAPORE_DATE = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  timeZone: "Asia/Singapore",
});

function seededDay(): string {
  const singapore = new Date(Date.now() + 8 * 60 * 60 * 1000);
  singapore.setUTCDate(singapore.getUTCDate() + 5);
  return singapore.toISOString().slice(0, 10);
}

/** A time as the screens show it, e.g. "12:15 PM". */
function shownTime(hhmm: string): string {
  const [hour, minute] = hhmm.split(":").map(Number);
  return `${hour % 12 || 12}:${String(minute).padStart(2, "0")} ${hour < 12 ? "AM" : "PM"}`;
}

/** The window as the screens show it, e.g. "Mon, Feb 1, 9:00 AM – 11:00 AM". */
function shownWindow(day: string, start: string, end: string): string {
  return `${SINGAPORE_DATE.format(new Date(`${day}T12:00:00+08:00`))}, ${shownTime(start)} – ${shownTime(end)}`;
}

async function openForm(page: Page) {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await expect(page.getByRole("heading", { name: "Review request" })).toBeVisible();
  await page.getByRole("region", { name: "Venue bookings" }).getByRole("button", { name: "Request venue" }).click();
}

async function fillWindow(page: Page, venue: string, day: string, start: string, end: string) {
  await page.getByLabel("Venue", { exact: true }).selectOption({ label: venue });
  // US24 (D66): every venue request says what the venue is for.
  await page.getByLabel("Purpose").fill("Main hall");
  await page.getByLabel("Date").fill(day);
  await page.getByLabel("Start time").fill(start);
  await page.getByLabel("End time").fill(end);
}

test("TC-US13-16: the form previews the window the chosen venue's setup and turnaround occupy (AC 2)", async ({ page }) => {
  await openForm(page);

  await fillWindow(page, "SCIS Seminar Room 2-1 (capacity 40)", seededDay(), "12:30", "13:30");
  await expect(
    page.getByText("The venue is occupied 12:15 PM – 1:45 PM (15 min setup, 15 min turnaround). Open 8:00 AM – 10:00 PM."),
  ).toBeVisible();

  // Another venue, its own buffers: Campus Green, Lawn C sets up for 90 minutes and turns around in 60.
  await page.getByLabel("Venue", { exact: true }).selectOption({ label: "Campus Green, Lawn C (capacity 200)" });
  await expect(page.getByText(/^The venue is occupied 11:00 AM – 2:30 PM \(90 min setup, 60 min turnaround\)/)).toBeVisible();

  // Nothing is sent until asked.
  await page.getByRole("button", { name: "Cancel" }).click();
});

test("TC-US13-17: an occupied window past closing is refused on the end time (AC 5)", async ({ page }) => {
  await openForm(page);

  // Li Ka Shing Library Seminar Room 3-4 closes at 18:00; its 20-minute turnaround runs 17:50 to 18:10.
  // Hours are checked before overlaps, so nothing is booked whatever else is on that day.
  await fillWindow(page, "Li Ka Shing Library Seminar Room 3-4 (capacity 60)", seededDay(), "16:30", "17:50");
  await page.getByLabel("Allocated attendees").fill("20");
  await page.getByLabel("Layout", { exact: true }).selectOption("classroom");
  await page.getByRole("button", { name: "Send request" }).click();

  await expect(page.getByRole("alert")).toContainText(
    "With setup and turnaround the venue would be occupied 4:10 PM – 6:10 PM, outside its opening hours of 9:00 AM – 6:00 PM.",
  );
  const end = page.getByLabel("End time");
  await expect(end).toHaveAttribute("aria-invalid", "true");
  await expect(end).toHaveAccessibleDescription("With turnaround, ends after the venue closes at 6:00 PM.");
  await expect(page.getByLabel("Start time")).not.toHaveAttribute("aria-invalid", "true");
});

test("TC-US13-17, 18, 19: setup inside a seeded booking's turnaround is refused with the overlap; touching is accepted and Venue staff see its occupied window (AC 2 to 4)", async ({ page }) => {
  const day = seededDay();
  await openForm(page);

  // 12:15–13:00 sets up from 12:00, inside the seeded booking's turnaround (to 12:15).
  await fillWindow(page, "SCIS Seminar Room 2-1 (capacity 40)", day, "12:15", "13:00");
  await page.getByLabel("Allocated attendees").fill("30");
  await page.getByLabel("Layout", { exact: true }).selectOption("classroom");
  await page.getByRole("button", { name: "Send request" }).click();

  await expect(page.getByRole("alert")).toContainText(
    `This venue is already booked on ${shownWindow(day, "10:00", "12:00")}. With setup and turnaround, that overlaps your request 12:00 PM – 12:15 PM.`,
  );
  await expect(page.getByLabel("Start time")).toHaveAccessibleDescription(
    "With setup and turnaround, overlaps another booking 12:00 PM – 12:15 PM.",
  );

  // 12:30 sets up from 12:15, exactly when the turnaround ends: touching windows are fine.
  await page.getByLabel("Start time").fill("12:30");
  await page.getByLabel("End time").fill("13:30");
  await expect(page.getByText(/^The venue is occupied 12:15 PM – 1:45 PM/)).toBeVisible();
  await page.getByRole("button", { name: "Send request" }).click();

  const window = shownWindow(day, "12:30", "13:30");
  const notice = page.getByRole("status").filter({ hasText: "Venue requested" });
  await expect(notice).toContainText(new RegExp(`SCIS Seminar Room 2-1, ${window} \\(VB-\\d{4}-\\d{6}\\)`));
  // The new booking's reference, from the notice: a rerun on the same database also lists earlier
  // runs' withdrawn bookings for this window, so its row is found by reference, not position.
  const reference = (await notice.textContent())?.match(/VB-\d{4}-\d{6}/)?.[0];
  expect(reference).toBeTruthy();
  const row = page
    .getByRole("region", { name: "Venue bookings" })
    .getByRole("listitem", { name: `SCIS Seminar Room 2-1, ${window}` })
    .filter({ hasText: reference! });
  await expect(row).toContainText(`${reference} · Occupied 12:15 PM – 1:45 PM with setup and turnaround`);

  // Venue staff see it with its reference and occupied window, and nothing in its way (AC 4).
  await page.getByLabel("Acting as").selectOption("venue_staff");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  const pending = page
    .getByRole("list", { name: "Pending venue requests" })
    .getByRole("listitem", { name: `${EVENT} at SCIS Seminar Room 2-1` })
    .filter({ hasText: reference! });
  await expect(pending).toContainText(`${reference} · Occupied 12:15 PM – 1:45 PM with setup and turnaround`);
  await expect(pending).toContainText("No conflicts with setup and turnaround.");
  // The seeded booking it touches isn't in conflict either.
  const seeded = page
    .getByRole("list", { name: "Pending venue requests" })
    .getByRole("listitem", { name: "Analytics Club Workshop at SCIS Seminar Room 2-1" })
    .filter({ hasText: shownWindow(day, "10:00", "12:00") });
  await expect(seeded).toContainText("Occupied 9:45 AM – 12:15 PM with setup and turnaround");
  await expect(seeded).toContainText("No conflicts with setup and turnaround.");

  // Tidy up, so a rerun on this database can book the same window.
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await row.getByRole("button", { name: "Withdraw" }).click();
  await page.getByRole("dialog", { name: "Withdraw this venue request?" }).getByRole("button", { name: "Withdraw request" }).click();
  await expect(row).toContainText("Withdrawn");
});
