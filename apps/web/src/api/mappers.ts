import type { ConsentRecord, ProtocolResult, TranscriptSegment } from "./types";
import type {
  WireConsentRecord,
  WireProtocolResult,
  WireTranscriptSegment,
} from "./wire";

export function consentFromWire(wire: WireConsentRecord): ConsentRecord {
  return {
    consentRef: wire.consent_ref,
    tenantId: wire.tenant_id,
    acceptedAt: wire.accepted_at,
    textVersion: wire.text_version,
  };
}

function segmentFromWire(wire: WireTranscriptSegment): TranscriptSegment {
  return {
    speaker: wire.speaker,
    text: wire.text,
    tStartMs: wire.t_start_ms,
    tEndMs: wire.t_end_ms,
    words: wire.words?.map((w) => ({
      word: w.word,
      tStartMs: w.t_start_ms,
      tEndMs: w.t_end_ms,
    })),
  };
}

export function protocolFromWire(wire: WireProtocolResult): ProtocolResult {
  return {
    protocolId: wire.protocol_id,
    sessionId: wire.session_id,
    consentRef: wire.consent_ref,
    createdAt: wire.created_at,
    durationMs: wire.duration_ms,
    speakers: wire.speakers,
    segments: wire.segments.map(segmentFromWire),
    summary: wire.summary,
    model: wire.model,
  };
}
