import { expect, test } from "@playwright/test";

test("home page shows backend health status", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Events at ConnectSphere" })).toBeVisible();
  await expect(page.getByText("Backend status:")).toBeVisible();
});
