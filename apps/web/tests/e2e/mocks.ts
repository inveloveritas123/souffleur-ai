import type { BrowserContext, Page } from "@playwright/test";

/**
 * Mock-Backend für die Playwright-E2E-Suite (Welle 9).
 *
 * apps/backend läuft hier bewusst NICHT — der REST-Vertrag aus
 * apps/web/src/api/wire.ts wird per page.route() mit realistischen
 * Fixtures simuliert (diarisiertes Protokoll inkl. Zusammenfassung).
 */

export const MOCK_CONSENT = {
  consent_ref: "consent-e2e-9f3a2b",
  tenant_id: "tenant-coach-demo",
  accepted_at: "2026-07-01T09:00:00.000Z",
  text_version: "2026-07-01",
};

export const MOCK_PROTOCOL = {
  protocol_id: "protocol-e2e-7c21",
  session_id: "session-e2e-1",
  consent_ref: MOCK_CONSENT.consent_ref,
  created_at: "2026-07-01T09:05:00.000Z",
  duration_ms: 184_000,
  speakers: ["coach", "counterpart"],
  segments: [
    {
      speaker: "coach",
      text: "Willkommen, lass uns über die Zielvereinbarung für dieses Quartal sprechen.",
      t_start_ms: 0,
      t_end_ms: 5200,
    },
    {
      speaker: "counterpart",
      text: "Gern, mir ist vor allem die Priorisierung der laufenden Projekte wichtig.",
      t_start_ms: 5400,
      t_end_ms: 11800,
    },
    {
      speaker: "coach",
      text: "Verstanden. Lass uns die drei wichtigsten Projekte gemeinsam einordnen.",
      t_start_ms: 12000,
      t_end_ms: 17650,
    },
  ],
  summary:
    "Coach und Gesprächspartner einigen sich auf eine Priorisierung der laufenden Projekte als " +
    "zentrales Ziel für das Quartal; nächste Schritte werden in einem Folgetermin konkretisiert.",
  model: {
    stt: "voxtral-mini-2602",
    reasoning: "magistral-medium-2509",
  },
};

/** Schritt 1: POST /api/v1/consent erfolgreich beantworten. */
export async function mockConsentEndpoint(page: Page): Promise<void> {
  await page.route("**/api/v1/consent", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_CONSENT),
    });
  });
}

/** Schritt 2: POST /api/v1/protocol — erfolgreicher Upload liefert das diarisierte Protokoll. */
export async function mockProtocolUploadSuccess(page: Page): Promise<void> {
  await page.route("**/api/v1/protocol", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_PROTOCOL),
    });
  });
}

/** Backend-ConsentGate-Verstoß: ohne (gültigen) Consent-Ref lehnt das Backend mit 403 ab. */
export async function mockProtocolUploadConsentRequired(page: Page): Promise<void> {
  await page.route("**/api/v1/protocol", async (route) => {
    if (route.request().method() !== "POST") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        code: "CONSENT_REQUIRED",
        detail: "Verarbeitung ohne dokumentierte Einwilligung (§201 StGB) abgelehnt.",
      }),
    });
  });
}

/** GET /api/v1/protocol/:id — Re-Fetch eines zuvor erzeugten Protokolls (z. B. nach Reload). */
export async function mockProtocolFetch(page: Page): Promise<void> {
  await page.route("**/api/v1/protocol/*", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(MOCK_PROTOCOL),
    });
  });
}

/**
 * Der PDF-Export (ProtocolView.exportAsPdf) öffnet ein Popup-Fenster und ruft
 * window.print() auf. In headless Chromium ist das harmlos, aber für einen
 * deterministischen Test stubben wir window.print auf Context-Ebene (gilt
 * laut Playwright-Doku auch für per window.open() erzeugte Popups) und
 * markieren den Aufruf über ein globales Flag.
 */
export async function stubPrintDialog(context: BrowserContext): Promise<void> {
  await context.addInitScript(() => {
    Object.defineProperty(window, "__printCalled", { value: false, writable: true });
    window.print = () => {
      (window as unknown as { __printCalled: boolean }).__printCalled = true;
    };
  });
}
