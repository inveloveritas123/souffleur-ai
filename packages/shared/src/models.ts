/**
 * Gepinnte Modell-IDs und STT-Provider-Werte (Single Source of Truth für Web/Overlay).
 *
 * Spiegelt apps/backend/src/souffleur/core/settings.py — Werte MÜSSEN exakt mit der
 * ARCHITECTURE.md-Tabelle "Modell-Routing & Pinning" und .env.example übereinstimmen
 * (Gate F1: niemals ein bewegliches "latest"-Tag; Gate E1: nur api.mistral.ai).
 */

/** Live-STT (Overlay, Phase 2) — SOUFFLEUR_MODEL_STT_LIVE */
export const MODEL_STT_LIVE = "voxtral-mini-transcribe-realtime-2602" as const;

/** Batch-STT + Diarisation (Protokoll, Phase 1) — SOUFFLEUR_MODEL_STT_BATCH */
export const MODEL_STT_BATCH = "voxtral-mini-2602" as const;

/** Reasoning / Coaching-Antwort — SOUFFLEUR_MODEL_REASONING */
export const MODEL_REASONING = "magistral-medium-2509" as const;

/** Trigger-Router (billig/schnell) — SOUFFLEUR_MODEL_TRIGGER */
export const MODEL_TRIGGER = "ministral-3b-2512" as const;

export const PINNED_MODELS = [
  MODEL_STT_LIVE,
  MODEL_STT_BATCH,
  MODEL_REASONING,
  MODEL_TRIGGER,
] as const;

/** Erlaubte Werte für SOUFFLEUR_STT_PROVIDER — Provider-Wechsel ist reine Config. */
export type SttProvider = "voxtral_api" | "voxtral_local" | "gladia";

export const STT_PROVIDER_VOXTRAL_API: SttProvider = "voxtral_api";
export const STT_PROVIDER_VOXTRAL_LOCAL: SttProvider = "voxtral_local";
export const STT_PROVIDER_GLADIA: SttProvider = "gladia";

/** Default gemäß .env.example (SOUFFLEUR_STT_PROVIDER). */
export const DEFAULT_STT_PROVIDER: SttProvider = STT_PROVIDER_VOXTRAL_API;

/** EU-Basis-URL — einziger erlaubter Mistral-Endpunkt (Gate E1). */
export const MISTRAL_BASE_URL = "https://api.mistral.ai" as const;

/** EU-Endpunkt (Frankreich) für den Gladia-Fallback — ebenfalls EU-zulässig. */
export const GLADIA_BASE_URL = "https://api.gladia.io" as const;
