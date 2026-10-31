import { expect, type Page, test } from "@playwright/test";

// US22 request a venue booking (SCRUM-89, PR 3 SCRUM-113). Books the seeded Approved event "Venue
// Booking Demo" (app.seed BOOKABLE_EVENT), which no other spec touches, so this spec creates its own
// rows (docs/testing/README.md): each test books a different seeded venue at its own hour, on a day
// 60 to 360 days ahead that changes from run to run, far from US2's seeded slot (five days ahead,
// venue-search.spec.ts reads it). Each test withdraws what it booked, so a rerun on the same
// database finds the window free again. Rows are found by venue and window, never by count.
const EVENT = "Venue Booking Demo";
const SINGAPORE_DATE = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  month: "short",
  day: "numeric",
  timeZone: "Asia/Singapore",
});

function runDay(): string {
  const offset = 60 + (Math.floor(Date.now() / 1000) % 300);
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
  await expect(page.getByRole("heading", { name: "Requests to review" })).toBeVisible();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  await expect(page.getByRole("heading", { name: "Review request" })).toBeVisible();
  return page.getByRole("region", { name: "Venue bookings" });
}

interface Request {
  venue: string;
  day: string;
  start: string;
  end: string;
  attendees?: string;
  layout: string;
}

async function fillRequest(page: Page, { venue, day, start, end, attendees, layout }: Request) {
  await page.getByRole("region", { name: "Venue bookings" }).getByRole("button", { name: "Request venue" }).click();
  await page.getByLabel("Venue", { exact: true }).selectOption({ label: venue });
  // US24 (D66): every venue request says what the venue is for.
  await page.getByLabel("Purpose").fill("Main hall");
  await page.getByLabel("Date").fill(day);
  await page.getByLabel("Start time").fill(start);
  await page.getByLabel("End time").fill(end);
  if (attendees) await page.getByLabel("Allocated attendees").fill(attendees);
  await page.getByLabel("Layout", { exact: true }).selectOption(layout);
}

function bookingRow(page: Page, venue: string, window: string) {
  // The newest of any same-named rows: the list is by start, then by when it was made.
  return page.getByRole("region", { name: "Venue bookings" }).getByRole("listitem", { name: `${venue}, ${window}` }).last();
}

async function withdraw(page: Page, venue: string, window: string) {
  const row = bookingRow(page, venue, window);
  await row.getByRole("button", { name: "Withdraw" }).click();
  await page.getByRole("dialog", { name: "Withdraw this venue request?" }).getByRole("button", { name: "Withdraw request" }).click();
  await expect(row).toContainText("Withdrawn");
}

test("TC-US22-19: a coordinator requests a venue for an approved event; Venue staff see it pending (AC 1, 2, 4)", async ({ page }) => {
  const day = runDay();
  const window = shownWindow(day, "09:00", "11:00");
  await openEvent(page);

  await fillRequest(page, { venue: "SCIS Seminar Room 2-1 (capacity 40)", day, start: "09:00", end: "11:00", attendees: "30", layout: "theatre" });
  await page.getByLabel("Special requirements").fill("Lectern at the front");
  await page.getByRole("button", { name: "Send request" }).click();

  await expect(page.getByRole("status").filter({ hasText: "Venue requested" })).toContainText(`SCIS Seminar Room 2-1, ${window}`);
  await expect(bookingRow(page, "SCIS Seminar Room 2-1", window)).toContainText("Requested");

  // Venue staff find it in their pending list.
  await page.getByLabel("Acting as").selectOption("venue_staff");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  const pending = page
    .getByRole("list", { name: "Pending venue requests" })
    .getByRole("listitem", { name: `${EVENT} at SCIS Seminar Room 2-1` })
    .filter({ hasText: window });
  await expect(pending).toContainText("30 attending");
  await expect(pending).toContainText("Lectern at the front");

  // Tidy up, so a rerun on this database can book the same window.
  await openEvent(page);
  await withdraw(page, "SCIS Seminar Room 2-1", window);
});

test("TC-US22-20: attendance over capacity is refused on the field; a missing layout warns but still sends (AC 3)", async ({ page }) => {
  const day = runDay();
  const window = shownWindow(day, "13:00", "15:00");
  await openEvent(page);

  // SMU Connexion Studio 3-2 seats 30 and offers boardroom, U-shape and classroom layouts.
  await fillRequest(page, { venue: "SMU Connexion Studio 3-2 (capacity 30)", day, start: "13:00", end: "15:00", attendees: "31", layout: "boardroom" });
  await page.getByRole("button", { name: "Send request" }).click();
  const attendance = page.getByLabel("Allocated attendees");
  await expect(attendance).toHaveAttribute("aria-invalid", "true");
  await expect(attendance).toHaveAccessibleDescription(/capacity of 30/);

  await attendance.fill("25");
  await page.getByLabel("Layout", { exact: true }).selectOption("theatre");
  await expect(page.getByText("This venue doesn't have: Theatre layout. You can still send the request.")).toBeVisible();
  await page.getByRole("button", { name: "Send request" }).click();

  const notice = page.getByRole("status").filter({ hasText: "Venue requested" });
  await expect(notice).toContainText(`SMU Connexion Studio 3-2, ${window}`);
  await expect(notice.getByRole("list", { name: "Warnings from the booking" })).toContainText(
    "This venue doesn't offer the theatre layout.",
  );

  await withdraw(page, "SMU Connexion Studio 3-2", window);
});

test("TC-US22-21: the coordinator confirms withdrawing a pending request, which shows as Withdrawn (AC 5)", async ({ page }) => {
  const day = runDay();
  // US13: the Library closes at 18:00 and its 20-minute turnaround must fit, so 15:00-17:00 (to 17:20).
  const window = shownWindow(day, "15:00", "17:00");
  await openEvent(page);

  await fillRequest(page, { venue: "Li Ka Shing Library Seminar Room 3-4 (capacity 60)", day, start: "15:00", end: "17:00", attendees: "20", layout: "classroom" });
  await page.getByRole("button", { name: "Send request" }).click();
  const row = bookingRow(page, "Li Ka Shing Library Seminar Room 3-4", window);
  await expect(row).toContainText("Requested");

  // Withdraw asks first, saying the window is freed to anyone at once; backing out keeps it.
  await row.getByRole("button", { name: "Withdraw" }).click();
  const dialog = page.getByRole("dialog", { name: "Withdraw this venue request?" });
  await expect(dialog).toContainText("The window is released straight away");
  await dialog.getByRole("button", { name: "Keep request" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(row).toContainText("Requested");

  await row.getByRole("button", { name: "Withdraw" }).click();
  await dialog.getByRole("button", { name: "Withdraw request" }).click();

  await expect(row).toContainText("Withdrawn");
  await expect(row.getByRole("button", { name: "Withdraw" })).toHaveCount(0);
  await expect(page.getByRole("status").filter({ hasText: "withdrawn" })).toContainText("Request for Li Ka Shing Library Seminar Room 3-4 withdrawn.");
});
