# RETENTION-DELETION — Souffleur AI

Aufbewahrungs- und Löschkonzept.

## Grundsatz

Datenminimierung und Speicherbegrenzung (Art. 5 Abs. 1 lit. c und e). Inhalte werden nur so lange aufbewahrt wie für den Zweck erforderlich.

## Fristen

| Datenart | Aufbewahrung | Löschauslöser |
|---|---|---|
| Roh-Audio | bis Transkriptionsende, längstens 24 Stunden | nach erfolgreicher Transkription |
| Transkript und Protokoll | konfigurierbar über Aufbewahrungstage, Vorgabe 30 Tage | Fristablauf oder Widerruf |
| Abgeleitete Coaching-Hinweise | wie Protokoll | Fristablauf oder Widerruf |
| Audit-Log-Metadaten | 90 Tage | Fristablauf |
| Einwilligungs-Nachweis | Dauer der Aufbewahrung plus gesetzliche Nachweisfrist | nach Ablauf der Nachweisfrist |

## Löschung

- Automatische Löschroutine entfernt abgelaufene Inhalte gemäß SOUFFLEUR_RETENTION_DAYS.
- Widerruf der Einwilligung löst unverzügliche Löschung von Audio, Transkript und abgeleiteten Inhalten aus (Audit-Metadaten bleiben als Nachweis pseudonym erhalten).
- Löschung erfolgt vollständig und nachweisbar; ein Löschvorgang erzeugt einen Audit-Eintrag mit action delete.

## Verantwortung

Die Einhaltung der Fristen ist technisch durchgesetzt (Löschroutine) und organisatorisch überwacht.
