import { defineConfig, devices } from "@playwright/test";

// Souffleur AI — Web-UI (Welle 9). E2E-Lauf gegen den Vite-Dev-Server, das
// Backend wird in jedem Test per page.route()-Mock simuliert (REST-Vertrag
// siehe src/api/wire.ts) — apps/backend läuft hier bewusst NICHT.
const PORT = Number(process.env.SOUFFLEUR_WEB_PORT ?? 5173);
const BASE_URL = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run dev",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
