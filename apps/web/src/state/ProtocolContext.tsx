import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { ProtocolResult } from "../api/types";

const STORAGE_KEY = "souffleur.protocol.latest.v1";

interface ProtocolContextValue {
  protocol: ProtocolResult | null;
  setProtocol: (protocol: ProtocolResult) => void;
  clearProtocol: () => void;
}

const ProtocolContext = createContext<ProtocolContextValue | undefined>(undefined);

function loadPersistedProtocol(): ProtocolResult | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as ProtocolResult) : null;
  } catch {
    return null;
  }
}

export function ProtocolProvider({ children }: { children: ReactNode }) {
  const [protocol, setProtocolState] = useState<ProtocolResult | null>(loadPersistedProtocol);

  const setProtocol = useCallback((next: ProtocolResult) => {
    setProtocolState(next);
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Anzeige funktioniert auch ohne Persistenz (z. B. Private-Mode/Tests).
    }
  }, []);

  const clearProtocol = useCallback(() => {
    setProtocolState(null);
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // siehe oben
    }
  }, []);

  const value = useMemo<ProtocolContextValue>(
    () => ({ protocol, setProtocol, clearProtocol }),
    [protocol, setProtocol, clearProtocol],
  );

  return <ProtocolContext.Provider value={value}>{children}</ProtocolContext.Provider>;
}

export function useProtocol(): ProtocolContextValue {
  const ctx = useContext(ProtocolContext);
  if (!ctx) {
    throw new Error("useProtocol muss innerhalb von <ProtocolProvider> verwendet werden.");
  }
  return ctx;
}
