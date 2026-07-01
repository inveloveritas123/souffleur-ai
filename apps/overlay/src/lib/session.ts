/**
 * session.ts — dünner Wrapper um die Tauri-Commands (`src-tauri/src/commands.rs`).
 *
 * Das Frontend kennt keine Audio-/WebSocket-Details — Capture (Mikrofon echt via cpal,
 * System-Audio als dokumentierter Stub) und die WS-Verbindung zu `/ws/v1/live` laufen
 * vollständig im Rust-Backend (siehe `src-tauri/src/capture`, `src-tauri/src/network`).
 */
import { invoke } from "@tauri-apps/api/core";

export interface StartSessionRequest {
  wsUrl: string;
  tenantId: string;
  sessionId: string;
  consentRef: string;
  sampleRate: number;
  language?: string;
}

export interface SessionStatus {
  active: boolean;
}

export async function startSession(request: StartSessionRequest): Promise<void> {
  await invoke("start_session", {
    request: {
      ws_url: request.wsUrl,
      tenant_id: request.tenantId,
      session_id: request.sessionId,
      consent_ref: request.consentRef,
      sample_rate: request.sampleRate,
      language: request.language,
    },
  });
}

export async function stopSession(): Promise<void> {
  await invoke("stop_session");
}

export async function getSessionStatus(): Promise<SessionStatus> {
  return await invoke<SessionStatus>("session_status");
}
