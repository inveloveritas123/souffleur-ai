# SPEC — Souffleur AI

> 6 Pflichtfelder (Gate A1). Akzeptanzkriterien testbar formuliert (Gate A2). Handoff PM→Architect (Gate A3).
> Quelle der Wahrheit für den Inhalt: `docs/concept/Konzept_Echtzeit_Coaching_Copilot.md`.
> Scope dieser Iteration: Variante 2 — Phase 1 (Async-Protokoll-MVP) + Phase 2 (Live-Overlay). Phase 3 nur Ausblick.

## 1. Ziel / Problem

Souffleur AI ist ein EU-souveräner, einwilligungsbasierter Echtzeit-Coaching-Copilot für 1:1-Gespräche (Coaching, Beratung, schwierige Gespräche). Der Coach erhält methodische Hinweise (Fragetechniken, Coaching-Frameworks) als unaufdringliche Karten — nicht Vertriebsskripte. Das Gegenüber erhält als Gegenleistung ein diarisiertes Protokoll. Das Produkt schließt eine reale Marktlücke: EU-souverän plus Echtzeit-Overlay plus Coaching-Methodik plus modular einbettbar — diese Kombination ist heute unbesetzt (Cluely/Glass sind US/Closed/Cheating-konnotiert, Sales-Copiloten sind vertrieblich und US-Cloud).

Zielnutzer sind Coaches und Berater im DACH-Raum, primär die ZUKUNFTSBUND-Organisation. Das Differenzierungsmerkmal und zugleich die rechtliche Absicherung ist die dokumentierte Einwilligung vor jeder Aufnahme (§ 201 StGB) und vollständige Transparenz (Anti-Cluely-Positionierung).

## 2. Scope (in / out)

- **In (Phase 1, Async-Protokoll-MVP):** Audio-Upload bzw. lokale Aufnahme eines beendeten Gesprächs; Batch-Transkription mit Diarisation und Wort-Zeitstempeln über das Modell voxtral-mini-2602; strukturierte Nachbereitung und Zusammenfassung über das Reasoning-Modell magistral-medium-2509; schlanke Web-UI zur Einwilligungs-Erfassung, zum Upload und zur Protokoll-Anzeige; Export des Protokolls als Markdown und PDF; Audit-Log jeder Verarbeitung (Schema gemäß `templates/AUDIT-LOG.schema.json`).
- **In (Phase 2, Live-Overlay):** Tauri-Overlay (macOS, screen-share-unsichtbar via NSWindow sharingType none); lokale Dual-Source-Capture (System-Audio gleich Gegenüber, Mikrofon gleich Coach); Live-Streaming-Transkription über das Modell voxtral-mini-realtime-2602; Transkript-Event-Bus zwischen Schicht 2 und Schicht 3 und 4; Trigger-Router (Regeln plus ministral-3b-2512) der entscheidet wann eine Karte sinnvoll ist; gestreamte Coaching-Karten über magistral-medium-2509 mit Wissen aus dem Coaching-MCP-Server.
- **In (querschnittlich):** STT als austauschbarer Port (Adapter voxtral_api als Default, voxtral_local als Kostenspar-Option auf Apple Silicon, gladia als gemessener Latenz-Fallback); Single-Provider Mistral (Paris) für STT und Reasoning über die Basis-URL api.mistral.ai; Coaching-Wissensschicht als MCP-Server; Docker und docker-compose für Backend, lokalen Voxtral-Worker und Frontend; Monorepo.
- **Out:** Fine-Tuning eigener Modelle (Wissen liegt im MCP-Server, nicht in Gewichten); Emotionserkennung oder Emotions-Scoring (EU AI Act Art. 5 Risiko — bewusst ausgeschlossen, Fokus auf inhaltliche Ableitungen); Cloud-Bot-Capture (Variante B, Phase 3); Windows- und Linux-Overlay (Phase 2 nur macOS Apple Silicon); Mehrmandantenfähigkeit als Produkt-Feature (Phase 3); produktiver Echtbetrieb mit echten Klientendaten vor juristischer Freigabe.

## 3. Datenarten & DSGVO-Relevanz

Das System verarbeitet personenbezogene Daten und mit hoher Wahrscheinlichkeit **besondere Kategorien nach Art. 9 DSGVO**: Coaching-Gespräche berühren psychische und gesundheitliche Themen, sodass Gesprächsinhalte sensible Daten darstellen. Verarbeitete Datenarten: Audiodaten (Stimme als biometriebehaftetes Rohmaterial), Transkripte mit Sprecher-Labels (Diarisation), abgeleitete Zusammenfassungen und Coaching-Hinweise, sowie Einwilligungs-Metadaten und Audit-Log-Einträge (pseudonymisiert).

Rechtsgrundlage: Art. 6 Abs. 1 lit. a (Einwilligung) in Verbindung mit Art. 9 Abs. 2 lit. a (ausdrückliche Einwilligung für besondere Kategorien). Die Einwilligung ist explizit, dokumentiert und zwingend vor Aufnahme (§ 201 StGB, Straftatbestand bei fehlender Einwilligung). Auftragsverarbeiter ist Mistral SAS, Paris (EU); keine Drittlandübermittlung. Wegen systematischer Verarbeitung sensibler Daten in Echtzeit ist eine Datenschutz-Folgenabschätzung nach Art. 35 DSGVO erforderlich. Die vollständigen DSGVO-Artefakte liegen im Verzeichnis `privacy/` (DATA-FLOW, PROCESSING-REGISTER, LAWFUL-BASIS, DPIA-SCREENING, DPIA, PROCESSORS-SUBPROCESSORS, THIRD-COUNTRY-TRANSFERS, RETENTION-DELETION, TOMs, DSAR-RIGHTS, BREACH-RUNBOOK). EU-Routing ist erzwungen (Gate E1), Klartext-PII in Logs und Prompts ist verboten (Gate E2).

## 4. Akzeptanzkriterien (testbar)

- [ ] Ein Verarbeitungslauf ohne zuvor erfasste, dokumentierte Einwilligung wird vom Backend mit HTTP 403 abgelehnt; ein automatisierter Test weist Ablehnung ohne Consent und Erfolg mit Consent nach.
- [ ] Jeder STT- und Reasoning-Aufruf erzeugt genau einen Audit-Log-Eintrag im Format von templates AUDIT-LOG.schema.json mit routing_region gleich EU und pii_present gleich false; der Gate-Check E4 läuft auf dem erzeugten Log grün.
- [ ] Das STT-Port-Interface erlaubt den Provider-Wechsel ausschließlich über die Umgebungsvariable SOUFFLEUR_STT_PROVIDER (Werte voxtral_api, voxtral_local, gladia); ein Test instanziiert alle drei Adapter ohne Codeänderung über die Factory.
- [ ] Die Phase-1-Batch-Transkription eines Test-Audios liefert ein Transkript mit mindestens zwei unterscheidbaren Sprecher-Labels und Wort-Zeitstempeln als strukturiertes JSON.
- [ ] Der Trigger-Router gibt für eine neutrale Aussage die Entscheidung keine Karte und für einen erkannten Einwand oder eine Frage die Entscheidung Karte zurück; beide Fälle sind als deterministischer Unit-Test (Regelpfad) abgedeckt.
- [ ] Kein Quell- oder Konfigurationsartefakt referenziert einen Non-EU-Endpunkt oder eine Non-EU-Region; der Gate-Check E1 läuft grün.
- [ ] Kein Modellbezeichner in Code oder Konfiguration verwendet das bewegliche latest-Tag; alle vier Modelle sind auf die gepinnten Versionen festgelegt und der Gate-Check F1 läuft grün.
- [ ] Das Tauri-Overlay setzt unter macOS die Fenster-Eigenschaft sharingType none, sodass es in einer Screen-Sharing-Aufnahme nicht erscheint; ein manuell dokumentierter Verifikationsschritt im Overlay-README beschreibt den Nachweis.
- [ ] Die Web-UI ist mit Playwright end-to-end testbar; ein E2E-Test durchläuft den Pfad Einwilligung erteilen, Audio hochladen, Protokoll anzeigen ohne Fehler.
- [ ] Die End-to-End-Latenz der Phase-2-Pipeline vom Ende einer Äußerung bis zum Beginn der sichtbaren Karte wird gemessen und dokumentiert; die Zielmarke liegt unter zwei Sekunden und ein Latenz-Messskript gibt einen reproduzierbaren Wert aus.

## 5. Nicht-Ziele / Annahmen

Nicht-Ziele: kein Selbst-Merge auf main (Mensch gibt frei); keine Speicherung echter Klientendaten in dieser Iteration; keine Garantie für Live-Latenz mit dem lokalen MLX-Adapter (Kostenspar-Option, nicht Latenz-Option); kein Gladia-Einsatz ohne vorherige Latenzmessung (Drop-in nur falls Voxtral-Realtime die Marke nicht hält).

Annahmen: Der Mistral-API-Zugang ist verifiziert verfügbar und der Schlüssel funktioniert (HTTP 200); die gepinnten Modelle voxtral-mini-realtime-2602, voxtral-mini-2602, magistral-medium-2509 und ministral-3b-2512 sind über die EU-Basis-URL api.mistral.ai erreichbar; die Zielhardware ist Apple Silicon (M5, 16 GB); juristische Freigabe durch Carsten Lexa (Einwilligungstext, DPIA, AI-Act-Einordnung, OSS-Lizenz-Check) erfolgt vor erstem Echtbetrieb und ist Voraussetzung für Phase-Live-Schaltung, nicht für den Bau der Artefakte; die Open-Source-Vorlage Pluely (Tauri) dient nur als Architektur-Referenz, Lizenz wird vor Übernahme einzeln geprüft.

## 6. Handoff PM → Architect (Gate A3)

- [x] Kontext dokumentiert: Vision, Marktlücke und Phasenmodell stammen aus dem Konzept; Scope dieser Iteration ist Variante 2 (Phase 1 plus Phase 2).
- [x] Constraints dokumentiert: Single-Provider Mistral Paris; vier gepinnte Modelle; STT als austauschbarer Port über SOUFFLEUR_STT_PROVIDER; EU-Routing erzwungen; Coaching-Wissen als MCP-Server statt Fine-Tuning; Stack FastAPI plus React-Vite plus Tauri plus Docker-Monorepo.
- [x] DSGVO-Rahmen dokumentiert: Art. 6 plus Art. 9 Einwilligung, DPIA erforderlich, Auftragsverarbeiter Mistral SAS Paris, keine Drittlandübermittlung; Artefakte in privacy.
- [x] Offene Entscheidungen benannt: gemessene Live-Latenz entscheidet über Gladia-Fallback; juristische Freigabe vor Echtbetrieb; Lizenzprüfung der OSS-Overlay-Basis.
- [x] Architektur-Artefakt erstellt: ARCHITECTURE.md beschreibt 4-Schichten-Architektur, STT-Port-Signaturen, Event-Bus-Schema, Trigger-Logik, Verzeichnislayout, Modell-Pinning und Docker-Topologie.
- [x] Build-Briefing erstellt: TASKS.md zerlegt die Arbeit in self-contained Wellen mit testbaren Akzeptanzkriterien je Welle.
