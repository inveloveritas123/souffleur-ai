/**
 * Bus-Event-Typen — gespiegelt aus `packages/shared/src/types.ts` /
 * `packages/shared/src/bus-event.schema.json` (Single Source of Truth bleibt dort; dieses
 * Overlay liest/kopiert nur, ändert `packages/shared` nicht, siehe Scope-Verbot).
 *
 * Diese Kopie existiert, weil `apps/overlay` kein Workspace-Package-Import auf
 * `packages/shared` einrichtet (kein Build-Tooling-Zugriff/Verbot laut Task-Scope) — bei
 * Drift zwischen beiden Kopien ist `packages/shared` die Wahrheit (ARCHITECTURE.md
 * "Drift-Kontrolle").
 */

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
  t_start_ms?: number;
  t_end_ms?: number;
}

export interface BusEvent {
  type: BusEventType;
  session_id: string;
  tenant_id: string;
  seq: number;
  ts_ms: number;
  payload: BusEventPayload;
  correlation_id: string;
}

export type ConnectionStatus = "idle" | "connecting" | "live" | "closed" | "error";

export interface TranscriptLine {
  speaker: BusEventSpeaker | "unknown";
  text: string;
  tsMs: number;
}

export type CoachingCardType = "einwand" | "frage" | "strukturhinweis" | string;

export interface CoachingCardState {
  correlationId: string;
  cardType?: CoachingCardType;
  text: string;
  complete: boolean;
  startedAtMs: number;
}
