import { expect, test } from "@playwright/test";

function daysFromNow(days: number): string {
  return new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

// US1 AC 3 (TC-US1-02, 03): save a partial draft, leave, come back to it with every value kept,
// then finish and submit. Unique per run, since a reused local database keeps every request.
test("organiser returns to a saved draft, edits it and submits", async ({ page }) => {
  const eventName = `Draft round-trip ${Date.now()}`;
  const firstDate = daysFromNow(30);
  const secondDate = daysFromNow(31);

  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: "Create request" }).click();

  await page.getByLabel("Event name").fill(eventName);
  await page.getByLabel("Event category").fill("Seminar");
  await page.getByRole("textbox", { name: "Preferred date" }).fill(firstDate);
  await page.getByRole("button", { name: "Add date" }).click();
  await page.getByRole("textbox", { name: "Preferred date" }).fill(secondDate);
  await page.getByRole("button", { name: "Add date" }).click();
  await expect(page.getByRole("list", { name: "Selected preferred dates" }).getByRole("listitem")).toHaveCount(2);
  // false must come back as "Not required", not as unset (TC-US1-03).
  await page.getByLabel("Attendee registration").selectOption("false");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("status")).toContainText("Draft saved");

  // Leave, and the list shows it as a draft with no reference yet (TC-US1-11).
  await page.getByRole("button", { name: "Back to my requests" }).click();
  const row = page.getByRole("button", { name: new RegExp(eventName) });
  await expect(row.locator(".request-status")).toHaveText("draft");
  await expect(row.locator(".request-row__reference")).toHaveCount(0);

  // A reload proves it came from the API, not component state.
  await page.reload();
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: new RegExp(eventName) }).click();
  await expect(page.getByLabel("Event name")).toHaveValue(eventName);
  await expect(page.getByLabel("Event category")).toHaveValue("Seminar");
  await expect(page.getByLabel("Attendee registration")).toHaveValue("false");
  const chips = page.getByRole("list", { name: "Selected preferred dates" });
  await expect(chips).toContainText(firstDate);
  await expect(chips).toContainText(secondDate);

  // Drop one date, finish the mandatory fields and submit.
  await page.getByRole("button", { name: `Remove ${secondDate}` }).click();
  await expect(chips.getByRole("listitem")).toHaveCount(1);
  // The picker still holds the first date, which is already added, so nothing is duplicated.
  await page.getByLabel("Purpose / description").fill("Share the semester plan");
  await page.getByLabel("Preferred start time").fill("10:00");
  await page.getByLabel("Preferred end time").fill("12:00");
  await page.getByLabel("Expected attendees").fill("25");
  await page.getByRole("button", { name: "Submit request" }).click();

  await expect(page.getByRole("heading", { level: 2, name: "Submission confirmed" })).toBeVisible();
  await expect(page.getByText(/ER-\d{4}-\d{6}/)).toBeVisible();

  // Back in the list it's submitted, with its reference, and opens read-only (TC-US1-12).
  await page.getByRole("button", { name: "Back to my requests" }).first().click();
  const submitted = page.getByRole("button", { name: new RegExp(eventName) });
  await expect(submitted.locator(".request-status")).toHaveText("submitted");
  await expect(submitted.locator(".request-row__reference")).toHaveText(/ER-\d{4}-\d{6}/);
  await submitted.click();
  await expect(page.getByRole("heading", { level: 2, name: "Submission confirmed" })).toBeVisible();
  await expect(page.getByLabel("Event name")).toHaveCount(0);
});
