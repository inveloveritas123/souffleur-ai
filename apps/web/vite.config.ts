import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Souffleur AI — Web-UI (Phase 1). Schlanker Build, kein schweres UI-Framework.
// Backend-Basis-URL kommt zur Laufzeit aus VITE_SOUFFLEUR_API_BASE (siehe src/config/env.ts),
// niemals hier hartkodiert.
export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.SOUFFLEUR_WEB_PORT ?? 5173),
  },
  preview: {
    port: Number(process.env.SOUFFLEUR_WEB_PORT ?? 5173),
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
