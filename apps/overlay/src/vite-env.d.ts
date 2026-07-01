/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SOUFFLEUR_WS_URL?: string;
  readonly VITE_SOUFFLEUR_TENANT_ID?: string;
  readonly VITE_SOUFFLEUR_LANGUAGE?: string;
  readonly VITE_SOUFFLEUR_CONSENT_REF?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
