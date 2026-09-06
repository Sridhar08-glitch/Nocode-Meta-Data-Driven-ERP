import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config (F1.3). Boots `next dev` and runs Chromium. The full
 * register→verify→login→MFA flow needs a live backend + the emailed token, so it is
 * guarded behind `E2E_FULL=1`; the always-on specs cover route protection + form UX.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run dev",
    url: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
