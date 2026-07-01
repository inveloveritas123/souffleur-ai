import { useCallback, useState } from "react";

import { ConsentBanner } from "./components/ConsentBanner";
import { CoachingCard } from "./components/CoachingCard";
import { SessionControls, type SessionFormValues } from "./components/SessionControls";
import { TranscriptStrip } from "./components/TranscriptStrip";
import { OVERLAY_CONFIG } from "./lib/config";
import { startSession, stopSession } from "./lib/session";
import { useLiveSession } from "./lib/useLiveSession";

/**
 * App — Wurzelkomponente des Overlays (Karten-Anzeige, Welle 16).
 *
 * Das gesamte Fenster ist ein `data-tauri-drag-region`, damit der Coach das Overlay trotz
 * `decorations:false` frei verschieben kann (kein Fenster-Rahmen nötig für die Drag-Geste).
 */
export function App() {
  const { status, transcript, activeCard, lastError, markConnecting, markIdle } = useLiveSession();
  const [startError, setStartError] = useState<string | null>(null);

  const handleStart = useCallback(
    (values: SessionFormValues) => {
      setStartError(null);
      markConnecting();
      startSession({
        wsUrl: values.wsUrl,
        tenantId: OVERLAY_CONFIG.tenantId,
        sessionId: values.sessionId,
        consentRef: values.consentRef,
        sampleRate: OVERLAY_CONFIG.sampleRate,
        language: OVERLAY_CONFIG.language,
      }).catch((err: unknown) => {
        setStartError(err instanceof Error ? err.message : String(err));
        markIdle();
      });
    },
    [markConnecting, markIdle],
  );

  const handleStop = useCallback(() => {
    stopSession()
      .catch(() => undefined)
      .finally(markIdle);
  }, [markIdle]);

  return (
    <div className="overlay-window" data-tauri-drag-region>
      <div className="overlay-window__top-row">
        <ConsentBanner status={status} />
        <SessionControls status={status} onStart={handleStart} onStop={handleStop} />
      </div>

      <TranscriptStrip lines={transcript} />
      <CoachingCard card={activeCard} />

      {(startError ?? lastError) && (
        <div className="overlay-window__error" role="alert" data-testid="overlay-error">
          {startError ?? lastError}
        </div>
      )}
    </div>
  );
}
