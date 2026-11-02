import { expect, test, type Locator } from "@playwright/test";

async function titles(agenda: Locator): Promise<string[]> {
  return agenda.getByRole("list", { name: "Sessions" }).getByRole("listitem").getByRole("heading").allTextContents();
}

// US15 (SCRUM-140): on the seeded Agenda Demo (planning, 09:00 to 17:00 Singapore time), the organiser adds a
// presentation and then an earlier break, and moves the presentation before the break. A rerun needs a reseed,
// which clears Agenda Demo's sessions (SCRUM-138).
test("TC-US15-15: the organiser builds Agenda Demo's agenda, which stays in time order (AC 1, 2, 5)", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption("organiser");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await page.getByRole("button", { name: /Agenda Demo/ }).click();
  const agenda = page.getByRole("region", { name: "Agenda" });
  await expect(agenda.getByText("No sessions yet.")).toBeVisible();

  await agenda.getByRole("button", { name: "Add session" }).click();
  let form = agenda.getByRole("form", { name: "Session" });
  await form.getByLabel("Title").fill("Opening keynote");
  await form.getByLabel("Speaker or presenter").fill("Dr Tan");
  await form.getByLabel("Start time").fill("11:00");
  await form.getByLabel("End time").fill("12:00");
  await form.getByRole("button", { name: "Save session" }).click();
  await expect(agenda.getByRole("button", { name: "Edit Opening keynote" })).toBeVisible();

  await agenda.getByRole("button", { name: "Add session" }).click();
  form = agenda.getByRole("form", { name: "Session" });
  await form.getByLabel("Title").fill("Coffee break");
  await form.getByLabel("Session type").selectOption("break");
  await form.getByLabel("Start time").fill("10:00");
  await form.getByLabel("End time").fill("10:15");
  await form.getByRole("button", { name: "Save session" }).click();
  await expect(agenda.getByRole("button", { name: "Edit Coffee break" })).toBeVisible();
  expect(await titles(agenda)).toEqual(["Coffee break", "Opening keynote"]);

  await agenda.getByRole("button", { name: "Edit Opening keynote" }).click();
  form = agenda.getByRole("form", { name: "Session" });
  await form.getByLabel("Start time").fill("09:00");
  await form.getByLabel("End time").fill("10:00");
  await form.getByRole("button", { name: "Save session" }).click();
  await expect(agenda.getByRole("button", { name: "Add session" })).toBeVisible();
  await expect(agenda.getByRole("list", { name: "Sessions" }).getByRole("listitem").first()).toContainText("Opening keynote");
  expect(await titles(agenda)).toEqual(["Opening keynote", "Coffee break"]);

  // Reopening shows the saved agenda, in the same order.
  await page.getByRole("button", { name: "Back to my requests" }).first().click();
  await page.getByRole("button", { name: /Agenda Demo/ }).click();
  await expect(agenda.getByRole("list", { name: "Sessions" }).getByRole("listitem").first()).toContainText("Opening keynote");
  expect(await titles(agenda)).toEqual(["Opening keynote", "Coffee break"]);
});
