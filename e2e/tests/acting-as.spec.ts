import { expect, test } from "@playwright/test";

// D12: the header's Acting as switch picks which seeded user's X-User-Id is sent, and the choice
// survives a reload (localStorage, per browser context, so this can't leak into other tests).
test("Acting as switches between the organiser's requests and the coordinator's queue, and is remembered", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await expect(page.getByRole("heading", { name: "My event requests" })).toBeVisible();

  await page.getByLabel("Acting as").selectOption("coordinator");
  await expect(page.getByRole("heading", { name: "Requests to review" })).toBeVisible();
  // The queue loaded for a coordinator: no FORBIDDEN or missing-id alert.
  await expect(page.getByRole("alert")).toHaveCount(0);

  await page.reload();
  await expect(page.getByLabel("Acting as")).toHaveValue("coordinator");
  await page.getByRole("banner").getByRole("button", { name: "Event requests" }).click();
  await expect(page.getByRole("heading", { name: "Requests to review" })).toBeVisible();

  await page.getByLabel("Acting as").selectOption("organiser");
  await expect(page.getByRole("heading", { name: "My event requests" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create request" })).toBeVisible();
});
