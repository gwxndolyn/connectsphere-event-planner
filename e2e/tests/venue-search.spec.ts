import { expect, type Page, test } from "@playwright/test";

// US2 search for suitable venues (SCRUM-7). Read-only against the seed: five days ahead, 10:00–12:00,
// SCIS Seminar Room 2-1 has a requested (tentatively held) booking, Mochtar Riady Auditorium an
// approved one, and SMU Connexion Studio 3-2 is blocked (app.seed VENUE_BOOKINGS, VENUE_BLOCKS). The
// day is Singapore's, as the seed computes it.
// Other specs add venues while this runs (venue-catalogue.spec.ts), so assert on named venues, never
// on how many results there are.
function seededDay(): string {
  const singapore = new Date(Date.now() + 8 * 60 * 60 * 1000);
  singapore.setUTCDate(singapore.getUTCDate() + 5);
  return singapore.toISOString().slice(0, 10);
}

async function openSearch(page: Page) {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  await expect(page.getByRole("heading", { name: "Find an available venue" })).toBeVisible();
}

async function search(page: Page, { date = seededDay(), start = "10:00", end = "12:00", attendees = "20" } = {}) {
  await page.getByLabel("Date").fill(date);
  await page.getByLabel("Start time").fill(start);
  await page.getByLabel("End time").fill(end);
  await page.getByLabel("Expected attendance").fill(attendees);
  await page.getByRole("button", { name: "Search venues" }).click();
}

function results(page: Page) {
  return page.getByRole("list", { name: "Available venues" });
}

test("TC-US2-13: held, booked and blocked venues drop out of the seeded slot (AC 1, 3, 4, 5)", async ({ page }) => {
  await openSearch(page);

  const started = Date.now();
  await search(page);
  await expect(results(page)).toBeVisible();
  // AC 8, end to end through the browser.
  expect(Date.now() - started).toBeLessThan(3000);

  // Only the seeded venues: venue-catalogue.spec.ts runs in parallel and may have just added one.
  const seeded = async () =>
    (await results(page).getByRole("listitem").evaluateAll((items) => items.map((item) => item.getAttribute("aria-label"))))
      .filter((name) => !name?.startsWith("E2E "));
  await expect.poll(seeded).toEqual(["Li Ka Shing Library Seminar Room 3-4", "Campus Green, Lawn C"]);
  for (const unavailable of ["SCIS Seminar Room 2-1", "Mochtar Riady Auditorium", "SMU Connexion Studio 3-2"]) {
    await expect(results(page).getByRole("listitem", { name: unavailable })).toHaveCount(0);
  }
  // Each result carries capacity, facilities and accessibility (AC 3).
  const library = results(page).getByRole("listitem", { name: "Li Ka Shing Library Seminar Room 3-4" });
  await expect(library).toContainText("60");
  await expect(library).toContainText("Projector, Screen, Wi-Fi");
  await expect(library).toContainText("Wheelchair, Lift");

  // The same venues come back on another day, when nothing is booked (AC 5 is about the slot).
  await page.getByLabel("Date").fill(
    new Date(Date.parse(seededDay()) + 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
  );
  await page.getByRole("button", { name: "Search venues" }).click();
  await expect(results(page).getByRole("listitem", { name: "SCIS Seminar Room 2-1" })).toBeVisible();
  await expect(results(page).getByRole("listitem", { name: "Mochtar Riady Auditorium" })).toBeVisible();
});

test("TC-US2-14: filters and operating hours narrow the results (AC 2, 6)", async ({ page }) => {
  await openSearch(page);
  const form = page.getByRole("region", { name: "Find an available venue" });

  // Library's seminar room closes at 18:00, Lawn C at 19:00 (AC 6).
  await search(page, { start: "17:30", end: "18:30" });
  await expect(results(page).getByRole("listitem", { name: "Campus Green, Lawn C" })).toBeVisible();
  await expect(results(page).getByRole("listitem", { name: "Li Ka Shing Library Seminar Room 3-4" })).toHaveCount(0);

  // Back to the seeded slot, then filter by location and a facility (AC 2).
  await search(page);
  await form.getByLabel("Location").fill("library");
  await form.getByRole("checkbox", { name: "Projector" }).check();
  await page.getByRole("button", { name: "Search venues" }).click();
  await expect(results(page).getByRole("listitem")).toHaveCount(1);
  await expect(results(page).getByRole("listitem", { name: "Li Ka Shing Library Seminar Room 3-4" })).toBeVisible();

  // An accessibility requirement the library room doesn't have.
  await form.getByRole("checkbox", { name: "Hearing loop" }).check();
  await page.getByRole("button", { name: "Search venues" }).click();
  await expect(page.getByText("No matching venues.")).toBeVisible();
});

test("TC-US2-15: no match says so and lists the criteria; bad input is marked (AC 7)", async ({ page }) => {
  await openSearch(page);

  await search(page, { attendees: "5000" });
  await expect(page.getByText("No matching venues.")).toBeVisible();
  const criteria = page.getByRole("list", { name: "Criteria applied" });
  await expect(criteria).toContainText(`Date: ${seededDay()}`);
  await expect(criteria).toContainText("Time: 10:00–12:00");
  await expect(criteria).toContainText("Expected attendance: 5000");

  await search(page, { start: "14:00", end: "12:00" });
  await expect(page.getByRole("alert")).toContainText("Review the fields marked below");
  await expect(page.getByLabel("End time")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByText("The end time must be after the start time")).toBeVisible();
});

test("TC-US2-16: organisers see the catalogue but not the search (D20)", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();

  await expect(page.getByRole("list", { name: "Venues" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Find an available venue" })).toHaveCount(0);
});
