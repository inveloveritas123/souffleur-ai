import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiClientError, recordConsent } from "../api/client";
import type { ConsentRecord } from "../api/types";

const STORAGE_KEY = "souffleur.consent.v1";

/** Aktuell gültige Fassung des Einwilligungstexts (§201 StGB — versioniert für die Dokumentation). */
export const CONSENT_TEXT_VERSION = "2026-07-01";

interface ConsentState {
  consent: ConsentRecord | null;
  status: "idle" | "submitting" | "error";
  error: string | null;
}

interface ConsentContextValue extends ConsentState {
  hasConsent: boolean;
  confirmConsent: (acknowledged: boolean) => Promise<void>;
  resetConsent: () => void;
}

const ConsentContext = createContext<ConsentContextValue | undefined>(undefined);

function loadPersistedConsent(): ConsentRecord | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as ConsentRecord;
  } catch {
    return null;
  }
}

function persistConsent(consent: ConsentRecord | null): void {
  try {
    if (consent) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(consent));
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // sessionStorage kann in manchen Testumgebungen fehlen — Consent bleibt dann nur in-memory.
  }
}

export function ConsentProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ConsentState>(() => ({
    consent: loadPersistedConsent(),
    status: "idle",
    error: null,
  }));

  /**
   * Pflicht-Schritt vor jedem Upload (§201 StGB): die Einwilligung wird beim
   * Backend dokumentiert (ConsentGate, Welle 2) und erst danach lokal als
   * "erteilt" markiert. Ohne erfolgreiche Backend-Bestätigung bleibt der
   * Upload-Schritt gesperrt.
   */
  const confirmConsent = useCallback(async (acknowledged: boolean) => {
    if (!acknowledged) {
      setState({
        consent: null,
        status: "error",
        error: "Bitte bestätige die Einwilligung, bevor du fortfährst.",
      });
      return;
    }

    setState((prev) => ({ ...prev, status: "submitting", error: null }));
    try {
      const consent = await recordConsent({
        participantAcknowledged: acknowledged,
        textVersion: CONSENT_TEXT_VERSION,
      });
      persistConsent(consent);
      setState({ consent, status: "idle", error: null });
    } catch (cause) {
      const message =
        cause instanceof ApiClientError
          ? cause.message
          : "Einwilligung konnte nicht dokumentiert werden. Bitte erneut versuchen.";
      setState({ consent: null, status: "error", error: message });
    }
  }, []);

  const resetConsent = useCallback(() => {
    persistConsent(null);
    setState({ consent: null, status: "idle", error: null });
  }, []);

  const value = useMemo<ConsentContextValue>(
    () => ({
      ...state,
      hasConsent: state.consent !== null,
      confirmConsent,
      resetConsent,
    }),
    [state, confirmConsent, resetConsent],
  );

  return <ConsentContext.Provider value={value}>{children}</ConsentContext.Provider>;
}

export function useConsent(): ConsentContextValue {
  const ctx = useContext(ConsentContext);
  if (!ctx) {
    throw new Error("useConsent muss innerhalb von <ConsentProvider> verwendet werden.");
  }
  return ctx;
}
