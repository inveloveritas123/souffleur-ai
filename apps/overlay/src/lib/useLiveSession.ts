/**
 * useLiveSession — React-Hook, der Tauri-Events (`souffleur://bus-event`/`-error`/`-status`,
 * siehe `src-tauri/src/network/mod.rs`) in UI-Zustand übersetzt: Transkript-Verlauf und
 * gestreamt aufgebaute Coaching-Karten.
 *
 * Cooldown/Spam-Schutz ist primär Backend-Sache (ARCHITECTURE.md "Trigger-Router-Logik") —
 * dieser Hook respektiert ihn zusätzlich auf der Anzeige-Seite: eine neue Karte übernimmt
 * den sichtbaren Platz erst, wenn die vorherige mindestens `CARD_MIN_DWELL_MS` sichtbar war
 * (kein hektisches Umspringen), siehe `flushQueueIfDue`.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { listen } from "@tauri-apps/api/event";

import { CARD_MIN_DWELL_MS, TRANSCRIPT_HISTORY_LIMIT } from "./config";
import type {
  BusEvent,
  CoachingCardState,
  ConnectionStatus,
  TranscriptLine,
} from "./types";

const BUS_EVENT = "souffleur://bus-event";
const SESSION_ERROR_EVENT = "souffleur://session-error";
const SESSION_STATUS_EVENT = "souffleur://session-status";

interface LiveSessionState {
  status: ConnectionStatus;
  transcript: TranscriptLine[];
  activeCard: CoachingCardState | null;
  lastError: string | null;
}

export function useLiveSession(): LiveSessionState & { markConnecting: () => void; markIdle: () => void } {
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [activeCard, setActiveCard] = useState<CoachingCardState | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  // Karten, die auf Anzeige warten (Cooldown-Dwell-Logik) — kein React-State, weil sich das
  // rein zeitgesteuert außerhalb des Render-Zyklus verändert.
  const cardsByCorrelation = useRef(new Map<string, CoachingCardState>());
  const pendingQueue = useRef<string[]>([]);
  const activeSince = useRef(0);

  const flushQueueIfDue = useCallback(() => {
    const now = Date.now();
    if (activeSince.current !== 0 && now - activeSince.current < CARD_MIN_DWELL_MS) {
      return;
    }
    const nextId = pendingQueue.current.shift();
    if (!nextId) return;
    const card = cardsByCorrelation.current.get(nextId);
    if (!card) return;
    activeSince.current = now;
    setActiveCard({ ...card });
  }, []);

  useEffect(() => {
    const timer = window.setInterval(flushQueueIfDue, 250);
    return () => window.clearInterval(timer);
  }, [flushQueueIfDue]);

  useEffect(() => {
    const unlistenBus = listen<BusEvent>(BUS_EVENT, (event) => {
      handleBusEvent(event.payload);
    });
    const unlistenError = listen<string>(SESSION_ERROR_EVENT, (event) => {
      setLastError(event.payload);
      setStatus("error");
    });
    const unlistenStatus = listen<string>(SESSION_STATUS_EVENT, (event) => {
      // Ein "closed" vom Transport darf einen bereits erkannten Fehler (z.B. abgelehnte
      // Einwilligung, siehe "error"-Fall unten) nicht überschreiben — sonst sieht der Coach
      // nur noch "beendet" statt des eigentlichen Grunds (Finding 8).
      if (event.payload === "closed") {
        setStatus((prev) => (prev === "error" ? prev : "closed"));
      }
    });

    // Setzt den Status nur bei echten Fortschritts-Events (Transkript/Karte) auf "live" — NIE
    // pauschal bei jeder eingehenden Nachricht, sonst überdeckt "live" kurz eine Backend-
    // `error`-Nachricht (Finding 8: Consent-Ablehnung wurde dadurch verschluckt).
    function markLive() {
      setStatus((prev) => (prev === "connecting" || prev === "idle" ? "live" : prev));
    }

    function handleBusEvent(evt: BusEvent) {
      if (evt.type === "error") {
        // Backend lehnt Handshake/Einwilligung ab (`api/live.py`: ungültiges JSON -> Close
        // 4400, fehlende/ungültige Einwilligung -> Close 4403) und sendet vorher `detail` als
        // für den Coach verständlichen Klartext-Grund.
        setLastError(evt.detail);
        setStatus("error");
        return;
      }

      switch (evt.type) {
        case "transcript.partial":
        case "transcript.final": {
          markLive();
          if (evt.type === "transcript.final" && evt.payload.text) {
            setTranscript((prev) => {
              const next: TranscriptLine[] = [
                ...prev,
                {
                  speaker: evt.payload.speaker ?? "unknown",
                  text: evt.payload.text ?? "",
                  tsMs: evt.ts_ms,
                },
              ];
              return next.slice(-TRANSCRIPT_HISTORY_LIMIT);
            });
          }
          break;
        }
        case "trigger.fired": {
          cardsByCorrelation.current.set(evt.correlation_id, {
            correlationId: evt.correlation_id,
            cardType: evt.payload.text,
            text: "",
            complete: false,
            startedAtMs: evt.ts_ms,
          });
          pendingQueue.current.push(evt.correlation_id);
          break;
        }
        case "card.streamed": {
          markLive();
          const existing = cardsByCorrelation.current.get(evt.correlation_id);
          const delta = evt.payload.text ?? "";
          if (existing) {
            existing.text += delta;
          } else {
            const created: CoachingCardState = {
              correlationId: evt.correlation_id,
              text: delta,
              complete: false,
              startedAtMs: evt.ts_ms,
            };
            cardsByCorrelation.current.set(evt.correlation_id, created);
            pendingQueue.current.push(evt.correlation_id);
          }
          setActiveCard((prev) =>
            prev && prev.correlationId === evt.correlation_id
              ? { ...prev, text: prev.text + delta }
              : prev,
          );
          break;
        }
        case "card.proposed": {
          markLive();
          const existing = cardsByCorrelation.current.get(evt.correlation_id);
          const fullText = evt.payload.text ?? existing?.text ?? "";
          const updated: CoachingCardState = {
            correlationId: evt.correlation_id,
            cardType: existing?.cardType,
            text: fullText,
            complete: true,
            startedAtMs: existing?.startedAtMs ?? evt.ts_ms,
          };
          cardsByCorrelation.current.set(evt.correlation_id, updated);
          setActiveCard((prev) => (prev && prev.correlationId === evt.correlation_id ? updated : prev));
          break;
        }
        case "session.closed": {
          setStatus("closed");
          break;
        }
        default:
          break;
      }
    }

    return () => {
      void unlistenBus.then((fn) => fn());
      void unlistenError.then((fn) => fn());
      void unlistenStatus.then((fn) => fn());
    };
  }, []);

  const markConnecting = useCallback(() => {
    setLastError(null);
    setStatus("connecting");
  }, []);
  const markIdle = useCallback(() => {
    setStatus("idle");
    setActiveCard(null);
    setTranscript([]);
    cardsByCorrelation.current.clear();
    pendingQueue.current = [];
    activeSince.current = 0;
  }, []);

  return { status, transcript, activeCard, lastError, markConnecting, markIdle };
}
