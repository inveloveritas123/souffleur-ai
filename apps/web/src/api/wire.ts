/**
 * "Wire"-Formate: so, wie das FastAPI-Backend (Python/Pydantic) JSON erwartet
 * bzw. liefert (snake_case). Die Domain-Typen in ./types.ts sind camelCase für
 * den UI-Code; ./mappers.ts übersetzt zwischen beiden Welten.
 *
 * Das Backend existiert zum Zeitpunkt von Welle 8 noch nicht (folgt aus W1-W6) —
 * dieses Modul ist der vereinbarte Vertrag, gegen den die Web-UI bereits tippt.
 */

export interface WireConsentRequest {
  participant_acknowledged: boolean;
  text_version: string;
}

export interface WireConsentRecord {
  consent_ref: string;
  tenant_id: string;
  accepted_at: string;
  text_version: string;
}

export interface WireWord {
  word: string;
  t_start_ms: number;
  t_end_ms: number;
}

export interface WireTranscriptSegment {
  speaker: string;
  text: string;
  t_start_ms: number;
  t_end_ms: number;
  words?: WireWord[];
}

export interface WireProtocolResult {
  protocol_id: string;
  session_id: string;
  consent_ref: string;
  created_at: string;
  duration_ms: number;
  speakers: string[];
  segments: WireTranscriptSegment[];
  summary: string;
  model: {
    stt: string;
    reasoning: string;
  };
}

export interface WireErrorBody {
  detail?: string;
  code?: string;
  message?: string;
}
