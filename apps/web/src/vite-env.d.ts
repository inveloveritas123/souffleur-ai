/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Basis-URL des Souffleur-Backends (FastAPI). Kein Secret, keine Modell-IDs hier —
   * nur die EU-lokale Backend-Adresse. Default in src/config/env.ts.
   */
  readonly VITE_SOUFFLEUR_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
