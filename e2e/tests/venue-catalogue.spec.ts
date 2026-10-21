import { expect, test } from "@playwright/test";

// US20 venue catalogue (SCRUM-87). Uses the seeded venues; see docs/testing/US20-venue-catalogue.md.

test("TC-US20-05: anyone signed in sees active venues and can search by name", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("button", { name: "Venues" }).click();

  const venues = page.getByRole("list", { name: "Venues" });
  await expect(venues.getByRole("listitem", { name: "Mochtar Riady Auditorium" })).toBeVisible();
  await expect(venues.getByRole("listitem", { name: "SCIS Seminar Room 2-1" })).toBeVisible();
  // The seeded inactive venue is hidden from everyone but Venue Staff (AC 3, 6).
  await expect(venues.getByRole("listitem", { name: "SOE Seminar Room B1-1" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add venue" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Edit" })).toHaveCount(0);

  await page.getByLabel("Search by name").fill("seminar");
  await expect(venues.getByRole("listitem", { name: "SCIS Seminar Room 2-1" })).toBeVisible();
  await expect(venues.getByRole("listitem", { name: "Mochtar Riady Auditorium" })).toHaveCount(0);
});

test("TC-US20-19: venue staff add, correct, edit and deactivate a venue", async ({ page }) => {
  // Unique per run: a reused local database keeps the venues earlier runs created.
  const venueName = `E2E Project Room ${Date.now()}`;

  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("venue_staff");
  await page.getByRole("button", { name: "Venues" }).click();
  await page.getByRole("button", { name: "Add venue" }).click();

  await page.getByLabel("Venue name").fill(venueName);
  await page.getByLabel("Location").fill("SCIS Building, Level 3");
  await page.getByLabel("Capacity", { exact: true }).fill("0");
  await page.getByLabel("Opens at").fill("09:00");
  await page.getByLabel("Closes at").fill("18:00");
  await page.getByRole("checkbox", { name: "Projector" }).check();
  await page.getByRole("checkbox", { name: "Wheelchair" }).check();
  await page.getByRole("button", { name: "Add venue" }).click();

  // The API's error names the field (AC 4).
  await expect(page.getByRole("alert")).toContainText("Review the fields marked below");
  await expect(page.getByText("Capacity must be greater than 0.")).toBeVisible();
  await expect(page.getByLabel("Capacity", { exact: true })).toHaveAttribute("aria-invalid", "true");

  await page.getByLabel("Capacity", { exact: true }).fill("35");
  await page.getByRole("button", { name: "Add venue" }).click();
  await expect(page.getByRole("status")).toContainText(`${venueName} saved.`);

  await page.getByLabel("Search by name").fill(venueName);
  const card = page.getByRole("list", { name: "Venues" }).getByRole("listitem", { name: venueName });
  await expect(card).toContainText("35");
  await expect(card).toContainText("Projector");

  await card.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Capacity", { exact: true }).fill("60");
  await page.getByLabel("Setup minutes").fill("20");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText(`${venueName} saved.`);
  await expect(card).toContainText("60");
  await expect(card).toContainText("20 / 0 min");

  await card.getByRole("button", { name: "Deactivate" }).click();
  await expect(card.getByText("Inactive")).toBeVisible();
  await expect(card.getByRole("button", { name: "Reactivate" })).toBeVisible();

  // Other roles no longer see it (AC 3).
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByLabel("Search by name").fill(venueName);
  await expect(page.getByText("No venues match these filters.")).toBeVisible();
});
