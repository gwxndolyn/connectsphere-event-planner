import { defineConfig, devices } from "@playwright/test";

const frontendPort = process.env.E2E_FRONTEND_PORT || "5173";
const frontendHost = process.env.E2E_FRONTEND_HOST || "localhost";
const frontendUrl = `http://${frontendHost}:${frontendPort}`;
// A second frontend with VITE_DEV_AUTH unset, so login is required (SCRUM-105, tests/login.spec.ts).
const loginPort = process.env.E2E_LOGIN_FRONTEND_PORT || "5174";
const loginUrl = `http://${frontendHost}:${loginPort}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: "html",
  use: {
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: /login\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], baseURL: process.env.E2E_BASE_URL || frontendUrl },
    },
    {
      name: "login",
      testMatch: /login\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], baseURL: loginUrl },
    },
  ],
  webServer: [
    {
      command: `npm run dev --prefix ../frontend -- --host ${frontendHost} --port ${frontendPort} --strictPort`,
      url: frontendUrl,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `npm run dev --prefix ../frontend -- --host ${frontendHost} --port ${loginPort} --strictPort`,
      url: loginUrl,
      reuseExistingServer: !process.env.CI,
      // An empty value overrides frontend/.env, so this server requires login.
      env: { ...process.env, VITE_DEV_AUTH: "" } as Record<string, string>,
    },
  ],
});
