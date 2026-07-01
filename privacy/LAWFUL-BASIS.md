# LAWFUL-BASIS — Souffleur AI

Rechtsgrundlagen der Verarbeitung.

## Primäre Rechtsgrundlage

- Art. 6 Abs. 1 lit. a DSGVO (Einwilligung) für die Verarbeitung personenbezogener Daten.
- Art. 9 Abs. 2 lit. a DSGVO (ausdrückliche Einwilligung) für besondere Kategorien, da Coaching-Gespräche psychische und gesundheitliche Themen berühren.

## Strafrechtlicher Rahmen

§ 201 StGB schützt die Vertraulichkeit des nicht-öffentlich gesprochenen Wortes. Das Aufzeichnen ohne Einwilligung ist eine Straftat. Daher ist die Einwilligung nicht nur datenschutzrechtlich, sondern strafrechtlich zwingend.

## Anforderungen an die Einwilligung

- Explizit, freiwillig, informiert und vor Aufnahme erteilt.
- Dokumentiert: hörbarer Hinweis zu Gesprächsbeginn plus Bestätigung per Klick mit gespeicherter Referenz-ID.
- Widerrufbar mit Wirkung für die Zukunft; Widerruf löst Löschung gemäß RETENTION-DELETION.md aus.
- Gegenleistung für das Gegenüber: diarisiertes Protokoll des Gesprächs.

## Nachweis

Das ConsentGate erzwingt eine gültige, dokumentierte Einwilligung vor jeder Verarbeitung. Ohne Nachweis erfolgt Ablehnung mit HTTP 403. Jeder Verarbeitungslauf trägt die Consent-Referenz.

## Hinweis zur Freigabe

Der konkrete Einwilligungstext und die AI-Act-Einordnung werden vor erstem Echtbetrieb juristisch geprüft (Carsten Lexa). Dies ist Voraussetzung der Live-Schaltung, nicht der Artefakt-Erstellung.
