/**
 * Zentrale Laufzeit-Konfiguration der Web-UI.
 *
 * Die Backend-Basis-URL kommt ausschließlich aus der Env-Variable
 * VITE_SOUFFLEUR_API_BASE (siehe .env.example / docker/docker-compose.yml).
 * Default ist das lokale Backend (SOUFFLEUR_BACKEND_PORT=8000 laut ARCHITECTURE.md).
 *
 * Harte Regel: hier wird niemals ein Non-EU-Endpunkt hartkodiert. Das Web-UI
 * spricht ausschließlich mit dem eigenen Souffleur-Backend, nie direkt mit
 * Mistral/Gladia — Modellaufrufe laufen serverseitig (Gate E1).
 */

const DEFAULT_API_BASE = "http://localhost:8000";

function readApiBase(): string {
  const fromEnv = import.meta.env.VITE_SOUFFLEUR_API_BASE?.trim();
  if (fromEnv && fromEnv.length > 0) {
    return stripTrailingSlash(fromEnv);
  }
  return DEFAULT_API_BASE;
}

function stripTrailingSlash(url: string): string {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

export const API_BASE_URL = readApiBase();

export const APP_CONFIG = {
  apiBaseUrl: API_BASE_URL,
} as const;
