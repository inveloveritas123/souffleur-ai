import { API_BASE_URL } from "../config/env";
import { consentFromWire, protocolFromWire } from "./mappers";
import type { ConsentRecord, ConsentRequest, ProtocolResult } from "./types";
import type {
  WireConsentRecord,
  WireConsentRequest,
  WireErrorBody,
  WireProtocolResult,
} from "./wire";

/**
 * Schlanker REST-Client zum Souffleur-Backend (apps/backend, FastAPI).
 *
 * Endpunkte (Vertrag für W6/Phase 1, siehe ARCHITECTURE.md):
 *  - POST {API_BASE_URL}/api/v1/consent             — Einwilligung dokumentieren (§201 StGB)
 *  - POST {API_BASE_URL}/api/v1/protocol            — Audio + consent_ref hochladen, Protokoll erzeugen
 *  - GET  {API_BASE_URL}/api/v1/protocol/{id}       — vorhandenes Protokoll erneut abrufen
 *
 * Die Web-UI spricht ausschließlich mit dem eigenen Backend (EU-lokal); kein
 * direkter Aufruf von Mistral/Gladia o.ä. aus dem Browser (Gate E1).
 */

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
  }

  /** §201/Consent-Verstoß — Backend lehnt Verarbeitung ohne dokumentierte Einwilligung ab. */
  get isConsentRequired(): boolean {
    return this.status === 403;
  }
}

async function parseErrorBody(response: Response): Promise<ApiClientError> {
  let body: WireErrorBody | undefined;
  try {
    body = (await response.json()) as WireErrorBody;
  } catch {
    body = undefined;
  }
  const message =
    body?.detail ?? body?.message ?? `Backend-Anfrage fehlgeschlagen (HTTP ${response.status}).`;
  const code = body?.code ?? `HTTP_${response.status}`;
  return new ApiClientError(response.status, code, message);
}

async function requestJson<TWire>(path: string, init: RequestInit): Promise<TWire> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new ApiClientError(
      0,
      "NETWORK_ERROR",
      "Souffleur-Backend nicht erreichbar. Läuft der Dienst unter der konfigurierten Basis-URL?",
    );
  }

  if (!response.ok) {
    throw await parseErrorBody(response);
  }

  return (await response.json()) as TWire;
}

/** Schritt 1 (Pflicht vor jeder Aufnahme/Verarbeitung): Einwilligung dokumentieren. */
export async function recordConsent(request: ConsentRequest): Promise<ConsentRecord> {
  const wireRequest: WireConsentRequest = {
    participant_acknowledged: request.participantAcknowledged,
    text_version: request.textVersion,
  };
  const wireResponse = await requestJson<WireConsentRecord>("/api/v1/consent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(wireRequest),
  });
  return consentFromWire(wireResponse);
}

/**
 * Schritt 2: Audio einer beendeten Aufnahme hochladen. Erfordert eine gültige
 * consentRef aus Schritt 1 — das Backend lehnt ohne diese mit HTTP 403 ab
 * (ConsentGate, siehe Welle 2/6).
 */
export async function uploadAudioForProtocol(
  audio: File | Blob,
  consentRef: string,
): Promise<ProtocolResult> {
  const formData = new FormData();
  const filename = audio instanceof File ? audio.name : "aufnahme.webm";
  formData.append("audio", audio, filename);
  formData.append("consent_ref", consentRef);

  const wireResponse = await requestJson<WireProtocolResult>("/api/v1/protocol", {
    method: "POST",
    body: formData,
  });
  return protocolFromWire(wireResponse);
}

/**
 * Schritt 3: ein zuvor erzeugtes Protokoll erneut laden (z. B. nach Reload).
 * Das Backend verlangt hierfür den `consent_ref` als Query-Param (Nachweis
 * der dokumentierten Einwilligung auch beim erneuten Abruf).
 */
export async function getProtocol(protocolId: string, consentRef: string): Promise<ProtocolResult> {
  const query = new URLSearchParams({ consent_ref: consentRef });
  const wireResponse = await requestJson<WireProtocolResult>(
    `/api/v1/protocol/${encodeURIComponent(protocolId)}?${query.toString()}`,
    { method: "GET" },
  );
  return protocolFromWire(wireResponse);
}
