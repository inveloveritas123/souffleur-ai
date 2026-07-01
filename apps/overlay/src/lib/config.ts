/**
 * Zentrale Laufzeit-Konfiguration des Overlays.
 *
 * Harte Regel (Gate E1, Task-Vorgabe): das Overlay spricht NUR das eigene Backend
 * (WebSocket, `SOUFFLEUR_BACKEND_PORT=8000` laut ARCHITECTURE.md) — niemals direkt
 * Mistral/Gladia oder einen anderen Non-EU-Endpunkt. Die WS-URL ist Env-konfigurierbar,
 * aber niemals ein hartkodierter Non-EU-Host als Default.
 *
 * `consentRef` hat bewusst KEINEN sinnvollen Default — Einwilligung ist Pflicht (§201 StGB)
 * und muss explizit aus dem Consent-Schritt (Web-UI Phase 1 oder ein zukünftiger
 * Overlay-eigener Consent-Schritt) übernommen werden, siehe SessionControls.tsx.
 */

function readEnv(name: string): string | undefined {
  const value = (import.meta.env as Record<string, string | undefined>)[name];
  const trimmed = value?.trim();
  return trimmed && trimmed.length > 0 ? trimmed : undefined;
}

const DEFAULT_WS_URL = "ws://localhost:8000/ws/v1/live";
const DEFAULT_TENANT_ID = "zukunftsbund";
const DEFAULT_LANGUAGE = "de";
const DEFAULT_SAMPLE_RATE = 16_000;

export const OVERLAY_CONFIG = {
  wsUrl: readEnv("VITE_SOUFFLEUR_WS_URL") ?? DEFAULT_WS_URL,
  tenantId: readEnv("VITE_SOUFFLEUR_TENANT_ID") ?? DEFAULT_TENANT_ID,
  language: readEnv("VITE_SOUFFLEUR_LANGUAGE") ?? DEFAULT_LANGUAGE,
  sampleRate: DEFAULT_SAMPLE_RATE,
  /** Nur als Vorbelegung fürs Formular gedacht — niemals automatisch als gültig behandeln. */
  defaultConsentRef: readEnv("VITE_SOUFFLEUR_CONSENT_REF") ?? "",
} as const;

/** Mindest-Anzeigedauer einer Karte (ms), bevor die nächste Karte den Platz übernimmt —
 * Anzeige-seitiges Cooldown-Verhalten (der eigentliche Trigger-Cooldown ist Backend-Sache,
 * ARCHITECTURE.md "Trigger-Router-Logik"; das hier verhindert nur hektisches Umspringen). */
export const CARD_MIN_DWELL_MS = 4_000;

/** Wie viele zuletzt gesehene Transkript-Segmente in der UI angezeigt werden. */
export const TRANSCRIPT_HISTORY_LIMIT = 4;
