import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  MOCK_PROTOCOL,
  mockConsentEndpoint,
  mockProtocolUploadSuccess,
  stubPrintDialog,
} from "./mocks";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_AUDIO_PATH = path.join(__dirname, "fixtures", "sample-session.wav");

/**
 * Welle 9 — Kern-Akzeptanz: Einwilligung erteilen → Audio hochladen →
 * Protokoll anzeigen läuft fehlerfrei gegen das gemockte Backend, und der
 * Export als Markdown bzw. PDF lässt sich auslösen.
 */
test.describe("Phase-1-Flow (Consent → Upload → Protokoll)", () => {
  test.beforeEach(async ({ page, context }) => {
    await stubPrintDialog(context);
    await mockConsentEndpoint(page);
    await mockProtocolUploadSuccess(page);
  });

  test("durchläuft Einwilligung, Upload und Protokoll-Anzeige ohne Fehler", async ({ page }) => {
    // Schritt 1: Einwilligung erteilen (Pflicht-Schritt vor Upload, §201 StGB).
    await page.goto("/consent");
    await expect(page.getByTestId("consent-view")).toBeVisible();

    await page.getByTestId("consent-checkbox").check();
    await page.getByTestId("consent-confirm-button").click();

    await expect(page.getByTestId("consent-success")).toBeVisible();
    await expect(page.getByTestId("consent-success")).toContainText("consent-e2e-9f3a2b");

    await page.getByTestId("consent-continue-button").click();
    await expect(page).toHaveURL(/\/upload$/);

    // Schritt 2: Audio hochladen.
    await expect(page.getByTestId("upload-view")).toBeVisible();
    await page.getByTestId("upload-file-input").setInputFiles(SAMPLE_AUDIO_PATH);

    const submitButton = page.getByTestId("upload-submit-button");
    await expect(submitButton).toBeEnabled();
    await submitButton.click();

    // Schritt 3: Protokoll wird angezeigt — diarisiert, mit Zusammenfassung.
    await expect(page).toHaveURL(/\/protocol$/);
    await expect(page.getByTestId("protocol-view")).toBeVisible();
    await expect(page.getByTestId("protocol-meta")).toContainText(MOCK_PROTOCOL.session_id);
    await expect(page.getByTestId("protocol-summary")).toContainText(MOCK_PROTOCOL.summary);

    const segments = page.getByTestId("protocol-segment");
    await expect(segments).toHaveCount(MOCK_PROTOCOL.segments.length);
    await expect(segments.first()).toContainText("coach");
    await expect(segments.nth(1)).toContainText("counterpart");

    await expect(page.getByTestId("upload-error")).toHaveCount(0);
    await expect(page.getByTestId("protocol-error")).toHaveCount(0);
  });

  test("Protokoll-Export als Markdown ist auslösbar (Download-Trigger)", async ({ page }) => {
    await page.goto("/consent");
    await page.getByTestId("consent-checkbox").check();
    await page.getByTestId("consent-confirm-button").click();
    await page.getByTestId("consent-continue-button").click();

    await page.getByTestId("upload-file-input").setInputFiles(SAMPLE_AUDIO_PATH);
    await page.getByTestId("upload-submit-button").click();
    await expect(page.getByTestId("protocol-view")).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-markdown-button").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`${MOCK_PROTOCOL.id}.md`);
  });

  test("Protokoll-Export als PDF ist auslösbar (Druckansicht öffnet sich)", async ({ page }) => {
    await page.goto("/consent");
    await page.getByTestId("consent-checkbox").check();
    await page.getByTestId("consent-confirm-button").click();
    await page.getByTestId("consent-continue-button").click();

    await page.getByTestId("upload-file-input").setInputFiles(SAMPLE_AUDIO_PATH);
    await page.getByTestId("upload-submit-button").click();
    await expect(page.getByTestId("protocol-view")).toBeVisible();

    const popupPromise = page.waitForEvent("popup");
    await page.getByTestId("export-pdf-button").click();
    const popup = await popupPromise;
    await popup.waitForLoadState();

    await expect(popup).toHaveTitle(new RegExp(MOCK_PROTOCOL.id));
    const printWasTriggered = await popup.evaluate(
      () => (window as unknown as { __printCalled: boolean }).__printCalled,
    );
    expect(printWasTriggered).toBe(true);

    await popup.close();
  });
});
