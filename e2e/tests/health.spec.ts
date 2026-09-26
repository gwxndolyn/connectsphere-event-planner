import { expect, test } from "@playwright/test";

test("home page loads and reaches the backend", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Events at ConnectSphere" })).toBeVisible();
  // The actual text, not just the label: this fails if the API is down or CORS blocks the call.
  await expect(page.getByText("event service is up")).toBeVisible();
});
