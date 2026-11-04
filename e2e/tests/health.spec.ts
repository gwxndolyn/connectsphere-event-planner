import { expect, test } from "@playwright/test";

test("home page loads and reaches the backend", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Events at ConnectSphere" })).toBeVisible();
  // The actual text, not just the label: this fails if the API is down or CORS blocks the call.
  await expect(page.getByText("event service is up")).toBeVisible();
});

// SCRUM-145: dev mode's header (every role's links plus Acting as) once made the page ~1767px wide.
for (const width of [1280, 1440]) {
  test(`the page doesn't scroll sideways at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/");
    await expect(page.getByLabel("Acting as")).toBeVisible();

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(width);
  });
}
