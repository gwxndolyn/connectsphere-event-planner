import { expect, type Page, test } from "@playwright/test";

// US26 equipment screens (SCRUM-110, story SCRUM-94). Adds lines to the seeded confirmed event
// "Equipment Request Demo" (app.seed EQUIPMENT_EVENT), which no other spec touches. An event has one
// pending or approved line per type (D41), so each test uses its own types. TC-US26-16 removes what it
// adds; TC-US26-17 approves a line, which can't be removed, so rerunning on the same database needs a
// reseed (`python -m app.seed`), which empties the demo event's equipment (docs/testing/README.md).
const EVENT = "Equipment Request Demo";

async function openEquipment(page: Page, role: "coordinator" | "tech_support") {
  await page.goto("/");
  await page.getByLabel("Acting as").selectOption(role);
  await page.getByRole("banner").getByRole("button", { name: "Equipment" }).click();
}

async function openEvent(page: Page) {
  await openEquipment(page, "coordinator");
  await page.getByLabel("Event", { exact: true }).selectOption({ label: EVENT });
  await expect(page.getByRole("region", { name: "Equipment lines" })).toBeVisible();
}

async function addLine(page: Page, type: string, quantity: string) {
  const add = page.getByRole("region", { name: "Add equipment" });
  await add.getByLabel("Equipment type").selectOption(type);
  await add.getByLabel("Quantity").fill(quantity);
  await add.getByRole("button", { name: "Add line" }).click();
}

function line(page: Page, type: string) {
  return page.getByRole("list", { name: "Equipment lines" }).getByRole("listitem", { name: type });
}

async function remove(page: Page, type: string) {
  await line(page, type).getByRole("button", { name: "Remove" }).click();
  await page.getByRole("dialog", { name: "Remove this equipment line?" }).getByRole("button", { name: "Remove line" }).click();
  await expect(line(page, type)).toHaveCount(0);
}

test("TC-US26-16: a coordinator adds a line, fixes the quantity, edits it, and adds and removes another (AC 1, 2, 4)", async ({ page }) => {
  await openEvent(page);
  const add = page.getByRole("region", { name: "Add equipment" });

  // Quantity 0: the API's refusal shows on the field, and nothing is added.
  await addLine(page, "Projector", "0");
  await expect(add.getByText("Quantity must be a whole number of at least 1.")).toBeVisible();
  await expect(line(page, "Projector")).toHaveCount(0);

  await add.getByLabel("Quantity").fill("2");
  await add.getByRole("button", { name: "Add line" }).click();
  await expect(line(page, "Projector")).toContainText("Pending");
  await expect(line(page, "Projector")).toContainText("Quantity 2");

  await line(page, "Projector").getByRole("button", { name: "Edit" }).click();
  const editing = page.getByRole("form", { name: "Edit Projector" });
  await editing.getByLabel("Quantity").fill("3");
  await editing.getByLabel("Notes").fill("One spare");
  await editing.getByRole("button", { name: "Save" }).click();
  await expect(line(page, "Projector")).toContainText("Quantity 3");
  await expect(line(page, "Projector")).toContainText("One spare");

  await addLine(page, "HDMI cable", "1");
  await expect(line(page, "HDMI cable")).toContainText("Pending");
  await remove(page, "HDMI cable");

  // Still there after a reload, then cleaned up so a rerun finds the type free.
  await openEvent(page);
  await expect(line(page, "Projector")).toContainText("Quantity 3");
  await remove(page, "Projector");
});

test("TC-US26-17: Tech support approves a pending line with a note; the coordinator sees it Approved (AC 3, 5)", async ({ page }) => {
  await openEvent(page);
  await addLine(page, "Wireless microphone", "2");
  await expect(line(page, "Wireless microphone")).toContainText("Pending");

  await openEquipment(page, "tech_support");
  await expect(page.getByRole("heading", { name: "Equipment requests to review" })).toBeVisible();
  const queued = page.getByRole("listitem", { name: `Wireless microphone for ${EVENT}` });
  await expect(queued).toContainText("Quantity 2");
  await queued.getByLabel("Note").fill("Two from the AV store");
  await queued.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("status")).toContainText(`Approved: Wireless microphone for ${EVENT}.`);
  await expect(queued).toHaveCount(0);

  // A fresh load: once the queue has loaded (other tests' lines may be in it), it no longer lists this one.
  await openEquipment(page, "tech_support");
  await expect(
    page.getByRole("list", { name: "Pending equipment requests" }).or(page.getByText("No equipment requests are waiting for review.")),
  ).toBeVisible();
  await expect(page.getByRole("listitem", { name: `Wireless microphone for ${EVENT}` })).toHaveCount(0);

  await openEvent(page);
  await expect(line(page, "Wireless microphone")).toContainText("Approved");
  await expect(line(page, "Wireless microphone")).toContainText("Tech support: Two from the AV store");
  await expect(line(page, "Wireless microphone").getByRole("button", { name: "Remove" })).toHaveCount(0);
});
