import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useConsent } from "../state/ConsentContext";

/**
 * Erzwingt im Web-UI dieselbe Reihenfolge wie das Backend (ConsentGate, §201 StGB):
 * kein Upload-Schritt ohne zuvor dokumentierte Einwilligung. Dies ist eine
 * UX-Absicherung — die verbindliche Durchsetzung bleibt serverseitig (HTTP 403).
 */
export function RequireConsent({ children }: { children: ReactNode }) {
  const { hasConsent } = useConsent();

  if (!hasConsent) {
    return <Navigate to="/consent" replace />;
  }

  return <>{children}</>;
}
