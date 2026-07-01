/**
 * SessionControls — minimales Start/Stop-Formular für die Live-Session.
 *
 * Bewusst schlank: die eigentliche, rechtsverbindliche Einwilligungs-ERFASSUNG (Checkbox,
 * Dokumentation, `consent_ref`-Ausstellung) passiert in der Web-UI (Phase 1,
 * `apps/web/src/views/ConsentView.tsx`) — dieses Formular nimmt nur eine bereits
 * ausgestellte `consent_ref` entgegen und startet/stoppt damit die Overlay-Session. Kein
 * Start ohne (nicht-leere) `consent_ref` möglich (Client-seitige Absicherung; die
 * verbindliche Prüfung macht ohnehin das Backend, `ConsentGate`, HTTP 403 ohne Consent).
 */
import { useState } from "react";

import { OVERLAY_CONFIG } from "../lib/config";
import type { ConnectionStatus } from "../lib/types";

export interface SessionFormValues {
  wsUrl: string;
  sessionId: string;
  consentRef: string;
}

interface Props {
  status: ConnectionStatus;
  onStart: (values: SessionFormValues) => void;
  onStop: () => void;
}

function newSessionId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `session-${Date.now()}`;
}

export function SessionControls({ status, onStart, onStop }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [wsUrl, setWsUrl] = useState(OVERLAY_CONFIG.wsUrl);
  const [sessionId, setSessionId] = useState(newSessionId());
  const [consentRef, setConsentRef] = useState(OVERLAY_CONFIG.defaultConsentRef);

  const isLive = status === "live" || status === "connecting";

  return (
    <div className="session-controls" data-testid="session-controls">
      <button
        type="button"
        className="session-controls__toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        title="Session-Einstellungen"
      >
        ⚙
      </button>

      {expanded && (
        <div className="session-controls__form">
          <label>
            Backend-WS-URL
            <input value={wsUrl} onChange={(e) => setWsUrl(e.target.value)} disabled={isLive} />
          </label>
          <label>
            Session-ID
            <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} disabled={isLive} />
          </label>
          <label>
            Consent-Referenz
            <input
              value={consentRef}
              onChange={(e) => setConsentRef(e.target.value)}
              placeholder="aus Web-UI-Einwilligung"
              disabled={isLive}
            />
          </label>
        </div>
      )}

      <button
        type="button"
        className="session-controls__action"
        disabled={!isLive && consentRef.trim().length === 0}
        onClick={() => (isLive ? onStop() : onStart({ wsUrl, sessionId, consentRef }))}
        data-testid="session-start-stop"
      >
        {isLive ? "Stop" : "Start"}
      </button>
    </div>
  );
}
