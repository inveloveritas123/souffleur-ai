/**
 * ConsentBanner — sichtbarer, dezenter Hinweis "KI-Assistenz aktiv (mit Einwilligung)".
 *
 * Anti-Cluely-Positionierung (Konzept-Dok Kap. 7 / TASKS.md Welle 16 "Entscheide"): das
 * Overlay verbirgt nur den PRIVATEN Hinweis-Layer des Coaches vor Screen-Sharing-Aufnahmen
 * (`sharingType=none`) — NICHT die Tatsache, dass eine KI-Verarbeitung stattfindet. Dieser
 * Banner ist deshalb im Overlay selbst (für den Coach) immer sichtbar, wenn eine Session
 * läuft, unabhängig davon, ob gerade eine Karte angezeigt wird. § 201 StGB/Transparenzpflicht
 * (EU AI Act) verlangen zusätzlich, dass das Gegenüber informiert ist — das passiert über den
 * separaten, dokumentierten Consent-Schritt (Web-UI Phase 1), nicht über dieses Overlay.
 */
import type { ConnectionStatus } from "../lib/types";

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  idle: "KI-Assistenz inaktiv",
  connecting: "KI-Assistenz verbindet …",
  live: "KI-Assistenz aktiv (mit Einwilligung)",
  closed: "KI-Assistenz beendet",
  error: "KI-Assistenz — Verbindungsfehler",
};

export function ConsentBanner({ status }: { status: ConnectionStatus }) {
  return (
    <div className={`consent-banner consent-banner--${status}`} role="status" data-testid="consent-banner">
      <span className="consent-banner__dot" aria-hidden="true" />
      <span>{STATUS_LABEL[status]}</span>
    </div>
  );
}
