/**
 * Lokale Spiegelung der für die Web-UI relevanten Backend-Typen
 * (siehe ARCHITECTURE.md, Abschnitt "Hilfstypen" / packages/shared).
 *
 * Welle 8 darf packages/shared nicht anfassen (Verbot laut TASKS.md), daher
 * liegt hier eine schlanke, eigenständige Kopie der Vertragstypen für den
 * Phase-1-Flow (Consent → Upload → Protokoll). Sobald packages/shared befüllt
 * ist, kann dieses Modul durch einen Re-Export ersetzt werden.
 */

/** Dokumentierte Einwilligung gemäß §201 StGB — Pflicht vor jeder Aufnahme/Verarbeitung. */
export interface ConsentRecord {
  consentRef: string;
  tenantId: string;
  acceptedAt: string; // ISO-8601
  textVersion: string;
}

export interface ConsentRequest {
  participantAcknowledged: boolean;
  textVersion: string;
}

export type Speaker = "coach" | "counterpart" | string;

/** Ein finales, diarisiertes Transkript-Segment mit Wort-Zeitstempeln. */
export interface TranscriptSegment {
  speaker: Speaker;
  text: string;
  tStartMs: number;
  tEndMs: number;
  words?: ReadonlyArray<{ word: string; tStartMs: number; tEndMs: number }>;
}

/** Ergebnis der Batch-Transkription (voxtral-mini-2602) plus Reasoning-Zusammenfassung. */
export interface ProtocolResult {
  protocolId: string;
  sessionId: string;
  consentRef: string;
  createdAt: string; // ISO-8601
  durationMs: number;
  speakers: ReadonlyArray<Speaker>;
  segments: ReadonlyArray<TranscriptSegment>;
  summary: string;
  model: {
    stt: string;
    reasoning: string;
  };
}

export interface ApiError {
  status: number;
  code: string;
  message: string;
}
