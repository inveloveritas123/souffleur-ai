import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  mockConsentEndpoint,
  mockProtocolUploadConsentRequired,
  mockProtocolUploadSuccess,
} from "./mocks";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_AUDIO_PATH = path.join(__dirname, "fixtures", "sample-session.wav");

/**
 * Welle 9 — Entscheide laut TASKS.md: "Einwilligung ist Pflicht-Schritt vor
 * Upload." Diese Suite prüft die Sperre aus zwei Richtungen: clientseitig
 * (RequireConsent-Redirect) und serverseitig (ConsentGate liefert 403).
 */
test.describe("Einwilligung als Pflicht-Schritt", () => {
  test("ohne Einwilligung kein Zugang zum Upload-Schritt (Redirect)", async ({ page }) => {
    // Frischer Browser-Context pro Test (Playwright-Default) → kein persistierter Consent.
    await page.goto("/upload");

    await expect(page).toHaveURL(/\/consent$/);
    await expect(page.getByTestId("consent-view")).toBeVisible();
    await expect(page.getByTestId("upload-view")).toHaveCount(0);
  });

  test("direkter Aufruf der Wurzel-Route leitet ebenfalls auf Einwilligung", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/consent$/);
    await expect(page.getByTestId("consent-view")).toBeVisible();
  });

  test("Backend lehnt Upload ohne dokumentierte Einwilligung mit HTTP 403 ab", async ({
    page,
  }) => {
    await mockConsentEndpoint(page);
    await mockProtocolUploadConsentRequired(page);

    await page.goto("/consent");
    await page.getByTestId("consent-checkbox").check();
    await page.getByTestId("consent-confirm-button").click();
    await page.getByTestId("consent-continue-button").click();
    await expect(page).toHaveURL(/\/upload$/);

    await page.getByTestId("upload-file-input").setInputFiles(SAMPLE_AUDIO_PATH);
    await page.getByTestId("upload-submit-button").click();

    await expect(page.getByTestId("upload-error")).toBeVisible();
    await expect(page.getByTestId("upload-error")).toContainText("Einwilligung");
    // Kein Wechsel zum Protokoll-Schritt nach abgelehntem Upload.
    await expect(page).toHaveURL(/\/upload$/);
  });

  test("erfolgreiche Einwilligung schaltet die Navigation zum Upload-Schritt frei", async ({
    page,
  }) => {
    await mockConsentEndpoint(page);
    await mockProtocolUploadSuccess(page);

    await page.goto("/consent");
    await expect(page.getByTestId("nav-upload")).toHaveAttribute("aria-disabled", "true");

    await page.getByTestId("consent-checkbox").check();
    await page.getByTestId("consent-confirm-button").click();
    await expect(page.getByTestId("consent-success")).toBeVisible();

    await expect(page.getByTestId("nav-upload")).toHaveAttribute("aria-disabled", "false");
    await page.getByTestId("nav-upload").click();
    await expect(page.getByTestId("upload-view")).toBeVisible();
  });
});
