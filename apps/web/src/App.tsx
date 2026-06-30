import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { RequireConsent } from "./components/RequireConsent";
import { ConsentProvider } from "./state/ConsentContext";
import { ProtocolProvider } from "./state/ProtocolContext";
import { ConsentView } from "./views/ConsentView";
import { ProtocolView } from "./views/ProtocolView";
import { UploadView } from "./views/UploadView";

/**
 * Phase-1-Flow (ARCHITECTURE.md): Einwilligung → Upload → Protokoll.
 * Die Reihenfolge ist hart verdrahtet: /upload ist nur über RequireConsent
 * erreichbar, das ohne dokumentierte Einwilligung auf /consent zurückleitet.
 */
export function App() {
  return (
    <ConsentProvider>
      <ProtocolProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/consent" replace />} />
            <Route path="consent" element={<ConsentView />} />
            <Route
              path="upload"
              element={
                <RequireConsent>
                  <UploadView />
                </RequireConsent>
              }
            />
            <Route path="protocol" element={<ProtocolView />} />
            <Route path="protocol/:protocolId" element={<ProtocolView />} />
            <Route path="*" element={<Navigate to="/consent" replace />} />
          </Route>
        </Routes>
      </ProtocolProvider>
    </ConsentProvider>
  );
}
