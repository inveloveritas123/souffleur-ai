import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Souffleur AI — Overlay (Tauri v2 Frontend).
// Tauri erwartet einen festen Dev-Server-Port und liest `dist/` als Build-Output
// (siehe src-tauri/tauri.conf.json: build.devUrl / build.frontendDist).
const OVERLAY_DEV_PORT = 1421;

export default defineConfig(() => ({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: OVERLAY_DEV_PORT,
    strictPort: true,
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    // macOS-only App -> WKWebView (modernes Safari). "safari13" als Ziel scheiterte an
    // einem Destructuring-Transform-Limit der hier verwendeten esbuild-Version — "es2021"
    // ist für das tatsächliche WKWebView-Zielsystem konservativ genug und baut zuverlässig.
    target: "es2021",
    minify: !process.env.TAURI_ENV_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
  },
}));
