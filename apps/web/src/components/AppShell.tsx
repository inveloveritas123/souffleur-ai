import { NavLink, Outlet } from "react-router-dom";
import { useConsent } from "../state/ConsentContext";

const navLinkClassName = ({ isActive }: { isActive: boolean }) =>
  isActive ? "nav-link nav-link--active" : "nav-link";

export function AppShell() {
  const { hasConsent } = useConsent();

  return (
    <div className="app-shell" data-testid="app-shell">
      <header className="app-header">
        <span className="app-title">Souffleur AI — Protokoll</span>
        <nav className="app-nav" aria-label="Phase-1-Schritte">
          <NavLink to="/consent" className={navLinkClassName} data-testid="nav-consent">
            1. Einwilligung
          </NavLink>
          <NavLink
            to="/upload"
            className={navLinkClassName}
            data-testid="nav-upload"
            aria-disabled={!hasConsent}
          >
            2. Aufnahme/Upload
          </NavLink>
          <NavLink to="/protocol" className={navLinkClassName} data-testid="nav-protocol">
            3. Protokoll
          </NavLink>
        </nav>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
