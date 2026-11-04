import { expect, type Page, test } from "@playwright/test";

// US20 AC 2 (SCRUM-147): Venue staff lower the Auditorium's capacity below the 400 the seeded Approved event "Venue
// Change Demo" (app.seed VENUE_CHANGE_EVENT, which only this spec uses) expects there; the coordinator sees its
// booking needs review, then Venue staff put the capacity back so reruns start the same. 399 still fits every other
// booking at the Auditorium (300) and the US2 search's 20, so parallel specs read it unchanged. A reseed also puts
// the capacity back, if a run stops in between.
const EVENT = "Venue Change Demo";
const VENUE = "Mochtar Riady Auditorium";
const SEEDED_CAPACITY = "450";

async function setCapacity(page: Page, capacity: string) {
  await page.getByLabel("Acting as").selectOption("venue_staff");
  await page.getByRole("banner").getByRole("button", { name: "Venues" }).click();
  await page.getByLabel("Search by name").fill(VENUE);
  const card = page.getByRole("list", { name: "Venues" }).getByRole("listitem", { name: VENUE });
  await card.getByRole("button", { name: "Edit" }).click();
  await page.getByLabel("Capacity", { exact: true }).fill(capacity);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText(`${VENUE} saved.`);
  await expect(card).toContainText(capacity);
}

test("TC-US20-29: Venue staff lower a venue's capacity; the coordinator sees the booking needs review (AC 2)", async ({ page }) => {
  await page.goto("/");
  try {
    await setCapacity(page, "399");

    // Venue staff are told which booking needs review.
    await page.getByRole("banner").getByRole("button", { name: /^Notifications/ }).click();
    await expect(
      page
        .getByRole("list", { name: "Notifications" })
        .getByRole("listitem")
        .filter({ hasText: "capacity is now 399, below the 400 expected" })
        .first(),
    ).toContainText(EVENT);

    // The coordinator sees it on the event's bookings; the booking itself is unchanged.
    await page.getByLabel("Acting as").selectOption("coordinator");
    await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
    await page.getByRole("button", { name: new RegExp(EVENT) }).click();
    const row = page.getByRole("region", { name: "Venue bookings" }).getByRole("listitem", { name: new RegExp(`^${VENUE}`) });
    await expect(row).toContainText("Needs review: the venue's capacity is now 399, below this booking's 400.");
    await expect(row).toContainText("400 attending");
    await expect(row).toContainText("Approved");
  } finally {
    await setCapacity(page, SEEDED_CAPACITY);
  }

  // With the capacity back, it no longer needs review.
  await page.getByLabel("Acting as").selectOption("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(EVENT) }).click();
  const row = page.getByRole("region", { name: "Venue bookings" }).getByRole("listitem", { name: new RegExp(`^${VENUE}`) });
  await expect(row).toContainText("400 attending");
  await expect(row).not.toContainText("Needs review");
});
