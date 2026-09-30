import { defineConfig, devices } from "@playwright/test";

const frontendPort = process.env.E2E_FRONTEND_PORT || "5173";
const frontendHost = process.env.E2E_FRONTEND_HOST || "localhost";
const frontendUrl = `http://${frontendHost}:${frontendPort}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: {
    baseURL: process.env.E2E_BASE_URL || frontendUrl,
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: `npm run dev --prefix ../frontend -- --host ${frontendHost} --port ${frontendPort} --strictPort`,
    url: frontendUrl,
    reuseExistingServer: !process.env.CI,
  },
});
