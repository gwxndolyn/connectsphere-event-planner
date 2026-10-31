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
  // The pending queue only: once approved, the line shows in the approved list below it (US27, SCRUM-132).
  const pending = page.getByRole("list", { name: "Pending equipment requests" });
  const queued = pending.getByRole("listitem", { name: `Wireless microphone for ${EVENT}` });
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
  await expect(pending.getByRole("listitem", { name: `Wireless microphone for ${EVENT}` })).toHaveCount(0);

  await openEvent(page);
  await expect(line(page, "Wireless microphone")).toContainText("Approved");
  await expect(line(page, "Wireless microphone")).toContainText("Tech support: Two from the AV store");
  await expect(line(page, "Wireless microphone").getByRole("button", { name: "Remove" })).toHaveCount(0);
});

// US5 (SCRUM-126). Uses Laptop and Speaker system, which no other test here touches, and removes both
// lines afterwards. Seeded stock (app.seed EQUIPMENT_STOCK): Laptop 8, none out of service, at the IT
// service desk; Speaker system 3 with 1 out of service, so 2 are available and 5 is short by 3.
test("TC-US5-11: Tech support checks availability: sufficient with the storage location, or short by the difference (AC 1, 4, 7)", async ({ page }) => {
  await openEvent(page);
  await addLine(page, "Laptop", "2");
  await expect(line(page, "Laptop")).toContainText("Pending");
  await addLine(page, "Speaker system", "5");
  await expect(line(page, "Speaker system")).toContainText("Pending");

  await openEquipment(page, "tech_support");
  const laptop = page.getByRole("listitem", { name: `Laptop for ${EVENT}` });
  await laptop.getByRole("button", { name: "Check availability" }).click();
  const laptopResult = laptop.getByRole("region", { name: "Availability" });
  await expect(laptopResult).toContainText("8 available for 2 requested: Sufficient");
  await expect(laptopResult).toContainText("Stored at IT service desk, Level 2, Administration Building");
  await expect(laptop).toContainText(/Last checked .*: Sufficient/);

  const speakers = page.getByRole("listitem", { name: `Speaker system for ${EVENT}` });
  await speakers.getByRole("button", { name: "Check availability" }).click();
  await expect(speakers.getByRole("region", { name: "Availability" })).toContainText("2 available for 5 requested: Short by 3");
  // A check only (AC 5): both lines are still waiting for review.
  await expect(speakers.getByRole("button", { name: "Approve" })).toBeEnabled();

  // Pending lines can be removed, so a rerun finds both types free (D41).
  await openEvent(page);
  await remove(page, "Laptop");
  await remove(page, "Speaker system");
});

// US27 (SCRUM-132). Uses Extension cord (seeded stock 15), which no other test here touches. An approved
// line can't be removed, so rerunning on the same database needs a reseed, as for TC-US26-17; the reseed
// removes the demo event's reservations with its lines (SCRUM-130).
test("TC-US27-18: Tech support reserves an approved line, the coordinator sees it Reserved, then it's released (AC 1, 4, 5)", async ({ page }) => {
  await openEvent(page);
  await addLine(page, "Extension cord", "1");
  await expect(line(page, "Extension cord")).toContainText("Pending");

  await openEquipment(page, "tech_support");
  await page.getByRole("listitem", { name: `Extension cord for ${EVENT}` }).getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("status")).toContainText(`Approved: Extension cord for ${EVENT}.`);
  const approved = page.getByRole("list", { name: "Approved equipment requests" }).getByRole("listitem", { name: `Extension cord for ${EVENT}` });
  await expect(approved).toContainText("Not reserved");
  await approved.getByRole("button", { name: "Reserve" }).click();
  await expect(approved).toContainText("Reserved");
  await expect(approved.getByRole("button", { name: "Release" })).toBeVisible();

  await openEvent(page);
  await expect(line(page, "Extension cord")).toContainText("Approved");
  await expect(line(page, "Extension cord")).toContainText("Reserved");

  await openEquipment(page, "tech_support");
  const again = page.getByRole("list", { name: "Approved equipment requests" }).getByRole("listitem", { name: `Extension cord for ${EVENT}` });
  await again.getByRole("button", { name: "Release" }).click();
  await expect(again).toContainText("Not reserved");
  await expect(again.getByRole("button", { name: "Reserve" })).toBeVisible();
});

// US14 (SCRUM-135). Uses Webcam, which no other test here touches, so the demo event has an
// approved technical support request (D80). An approved line can't be removed, so rerunning on the same
// database needs a reseed, as for TC-US26-17; the reseed clears the demo event's assignments (SCRUM-133).
test("TC-US14-17: the coordinator assigns Terry Ong, then unassigns him; the log shows both (AC 1, 3, 5, 6)", async ({ page }) => {
  await openEvent(page);
  await addLine(page, "Webcam", "1");
  await expect(line(page, "Webcam")).toContainText("Pending");

  await openEquipment(page, "tech_support");
  await page.getByRole("listitem", { name: `Webcam for ${EVENT}` }).getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("status")).toContainText(`Approved: Webcam for ${EVENT}.`);

  await openEvent(page);
  const section = page.getByRole("region", { name: "Technical support" });
  const assigned = section.getByRole("list", { name: "Assigned Tech support staff" });
  await section.getByRole("checkbox", { name: "Terry Ong" }).check();
  await section.getByRole("button", { name: "Assign" }).click();
  await expect(assigned.getByRole("listitem", { name: "Terry Ong" })).toContainText("Assigned by Casey Tan");

  await assigned.getByRole("button", { name: "Unassign Terry Ong" }).click();
  await expect(section.getByRole("checkbox", { name: "Terry Ong" })).toBeVisible();
  await expect(section.getByText("No one assigned yet.")).toBeVisible();
  const log = section.getByRole("list", { name: "Assignment log" }).getByRole("listitem");
  await expect(log.nth(0)).toContainText("Terry Ong unassigned by Casey Tan");
  await expect(log.nth(1)).toContainText("Terry Ong assigned by Casey Tan");
});
