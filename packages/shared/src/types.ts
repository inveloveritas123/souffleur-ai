/**
 * Geteilte Datentypen über die Schicht-Grenzen hinweg (Single Source of Truth).
 *
 * Backend spiegelt dieselben Strukturen in Python: `apps/backend/src/souffleur/ports/types.py`
 * (STT-Hilfstypen) und das Event-Bus-Schema unten. Siehe ARCHITECTURE.md
 * "STT-Port-Interface" und "Event-Bus-Schema". Diese Typen tragen niemals Audio-Rohdaten
 * oder Klartext-PII in persistierten Log-Strukturen (Gate E2).
 */

/** Kontext einer Transkriptions-Session (Phase 1 Batch oder Phase 2 Live-Stream). */
export interface SessionContext {
  tenantId: string;
  sessionId: string;
  /** Referenz auf eine dokumentierte Einwilligung (§201 StGB ConsentGate). */
  consentRef: string;
  sampleRate: number;
  /** 2 für Dual-Source (System-Audio = Gegenüber, Mikrofon = Coach). */
  channels: number;
  language?: string;
}

/** Provider-internes Handle für eine offene Live-Stream-Session. */
export interface StreamHandle {
  providerHandle: string;
  correlationId: string;
}

/** Ein Wort-Zeitstempel innerhalb eines Transkript-Segments. */
export interface Word {
  text: string;
  tStartMs: number;
  tEndMs: number;
}

export type TranscriptEventKind = "partial" | "final";

/** Ein partielles oder finales Transkript-Segment mit Sprecher-Label. */
export interface TranscriptEvent {
  kind: TranscriptEventKind;
  speaker: string;
  text: string;
  tStartMs: number;
  tEndMs: number;
  words?: Word[];
}

/** Ergebnis einer Batch-Transkription oder einer geschlossenen Live-Stream-Session. */
export interface TranscriptResult {
  segments: TranscriptEvent[];
  speakers: string[];
  durationMs: number;
  model: string;
  provider: string;
}

/** Metadaten eines STT-Adapters — erlaubt latenz-/feature-bewusstes Routing. */
export interface ProviderCapabilities {
  supportsStreaming: boolean;
  supportsDiarization: boolean;
  supportsWordTimestamps: boolean;
  typicalFinalLatencyMs: number;
  /** Muss "EU" sein (Gate E1) — voxtral_local kann zusätzlich rein lokal laufen. */
  residency: string;
}

/** Referenz auf eine Audio-Quelle (lokaler Pfad oder Stream) — niemals Audio im Log. */
export interface AudioRef {
  localPath?: string;
  streamSource?: string;
}

/** Optionen für die Phase-1-Batch-Transkription (Diarisation, Wort-Zeitstempel). */
export interface BatchOptions {
  diarization: boolean;
  wordTimestamps: boolean;
  language?: string;
  numSpeakersHint?: number;
}

/** Event-Typen des TranscriptEventBus (ARCHITECTURE.md "Event-Bus-Schema", Welle 11). */
export type BusEventType =
  | "transcript.partial"
  | "transcript.final"
  | "trigger.fired"
  | "card.proposed"
  | "card.streamed"
  | "session.closed";

export type BusEventSpeaker = "coach" | "counterpart";

export interface BusEventPayload {
  speaker?: BusEventSpeaker;
  text?: string;
  tStartMs?: number;
  tEndMs?: number;
}

/** Ein einzelnes Bus-Event — async pub/sub pro Session (siehe bus-event.schema.json). */
export interface BusEvent {
  type: BusEventType;
  sessionId: string;
  tenantId: string;
  seq: number;
  tsMs: number;
  payload: BusEventPayload;
  correlationId: string;
}
