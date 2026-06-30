# Echtzeit-Coaching-Copilot — Marktanalyse & tragfähiges Konzept

**Stand:** 01.07.2026 · **Autor:** für Robert / ZUKUNFTSBUND · **Status:** Konzept v1 zur Bewertung

---

## 0. Kernthese (TL;DR)

Es gibt **kein** fertiges Produkt, das deine vier Anforderungen gleichzeitig erfüllt: (1) Echtzeit-Copilot mit semitransparentem Overlay, (2) Coaching-Methodik statt Sales-Skripte, (3) EU-souverän/DSGVO-konform über APIs, (4) als Modul einbettbar. Die Bausteine **einzeln** sind dagegen reife Commodity — sowohl als API als auch Open Source.

**Empfehlung:** Nicht alles selbst bauen. Die Commodity-Schichten (Audio-Capture, STT, Diarisation, LLM) über **DSGVO-konforme EU-APIs** beziehen — primär **Gladia** (STT, Frankreich, 100 % EU-Residency) + **Mistral** (Reasoning, Paris). Selbst bauen: die **Wissensschicht** (Coaching-Konzepte), die **Trigger-/Reasoning-Logik** und das **Overlay**. Das Overlay ist der einzige lokale Bestandteil — als schlanke Tauri-App (~10 MB), für die es ausgereifte Open-Source-Vorlagen gibt.

**Das ist ein klares ZUKUNFTSBUND-Produkt/Modul.** Die Marktlücke (EU-souverän + Echtzeit-Overlay + Coaching + modular) ist real und unbesetzt.

**Wichtigster Vorbehalt:** Die „unsichtbares Overlay"-Technik kommt 1:1 aus der Cheating-Tool-Ecke (Cluely & Co.). Eure Legitimität steht und fällt mit **Einwilligung + Transparenz** — das ist nicht nur DSGVO, das ist **§ 201 StGB (Strafrecht)**. Mehr dazu in Kapitel 7. Das ist gleichzeitig euer schärfstes Differenzierungsmerkmal gegen Cluely.

---

## 1. Referenzarchitektur

Vier entkoppelte Schichten. Die Schnittstelle zwischen ihnen (ein Transkript-/Event-Stream) ist das, was du später als Modul woanders andockst.

```
┌─────────────────────────────────────────────────────────────────┐
│  1. CAPTURE          2. TRANSCRIBE        3. REASONING            │
│  ┌────────────┐      ┌──────────────┐     ┌──────────────────┐    │
│  │ System-    │      │ Gladia STT   │     │ Trigger-Router   │    │
│  │ Audio +Mic │─PCM─▶│ (EU, ~270ms) │────▶│ (wann Karte?)    │    │
│  │ (Overlay)  │      │ +Diarisation │     │       │          │    │
│  └────────────┘      └──────────────┘     │       ▼          │    │
│        ODER                               │ Mistral + MCP-   │    │
│  ┌────────────┐                           │ Wissensschicht   │    │
│  │ Cloud-Bot  │                           │ (Coaching-Konz.) │    │
│  │ Vexa/Recall│                           └────────┬─────────┘    │
│  └────────────┘                                    │              │
│                                                    ▼              │
│  4. DISPLAY: Semitransparentes Overlay (unten eingeblendet)       │
│     ┌───────────────────────────────────────────────────────┐    │
│     │  💡 Gegenüber nennt 3× Zeitdruck, vermeidet Budget     │    │
│     │  → "Was müsste sich ändern, damit Zeit kein Thema..."  │    │
│     └───────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
        Lokal (Overlay-App)        EU-Cloud-APIs (DSGVO)      Lokal
```

**Designprinzip:** Das LLM läuft **nicht** auf jeder Äußerung. Ein leichter Trigger-Router entscheidet, *wann* eine Karte sinnvoll ist (Einwand, Frage, längere Pause, Schlüsselbegriff). Das spart Kosten, Latenz und — entscheidend — kognitive Last beim Coach. So machen es auch die Sales-Tools mit ihren „Real-Time-Assist-Cards".

---

## 2. Marktanalyse & Open Source je Baustein

### 2.1 Capture — Audio aus Teams/Meet/Zoom

Zwei grundsätzliche Wege: **Cloud-Bot** (tritt der Konferenz bei) oder **lokale Capture** (Overlay greift System-Audio + Mic ab). Für die Capture-Infrastruktur als Service/OSS:

| Lösung | Lizenz/Modell | Plattformen | Pro-Speaker-Audio | EU/DSGVO | Preis | Bewertung |
|---|---|---|---|---|---|---|
| **Recall.ai** | Closed, SaaS | Zoom/Teams/Meet/Webex/Slack u.v.m. | ja (Konfig) | SOC2/ISO27001/GDPR, US-Firma | ~$0,50/h | Goldstandard Zuverlässigkeit (99,9 % SLA), aber **US-Cloud** |
| **Vexa** | **Apache 2.0 (OSS)** | Meet + Teams (Zoom kommt) | ja (Diarisation, WebSocket) | self-hostbar → volle Kontrolle; **MCP-nativ** | $0,30/h Cloud / self-host gratis | **Bester Fit für dich** (OSS, MCP, EU-hostbar) |
| **Attendee.dev** | **OSS** | Zoom/Teams/Meet | ja (PCM16 first-class) | self-hostbar | self-host | Solide OSS-Alternative, mehr DevOps |
| **MeetStream** | SaaS | Zoom/Teams/Meet | ja (PCM16 pro Speaker) | — | usage | In-Meeting-Agent-Support |
| **MeetingBaaS** | SaaS | Zoom/Teams/Meet | ja | — | Token-Modell | Dev-freundlich |
| **Skribby** | SaaS | Zoom/Teams/Meet | ja | — | $0,35/h | Günstig, Gründer-Support |

**OSS-Empfehlung Capture:** **Vexa** (Apache 2.0). Selten passt etwas so genau auf deine Welt: Open Source, self-hostbar (EU-Kontrolle), MCP-nativ (du kannst Live-Meeting-Daten direkt an deine MCP-Clients hängen), Sub-Sekunden-Latenz, Speaker-Diarisation über WebSocket. Migration von Recall ist laut Vexa nahezu drop-in (gleiche REST-Form). Einschränkung: Zoom noch nicht (kommt), Teams + Meet ja.

**Wichtig für die Architektur-Entscheidung:** Den **Bot brauchst du nur, wenn du Gruppen-Settings mit sauberer Mehr-Sprecher-Trennung bedienst** oder einen sichtbaren „Consent-Bot" willst. Für **1:1-Coaching** ist die lokale Capture im Overlay (System-Audio = Gegenüber, Mic = Coach) der kürzere, latenzärmere Weg — und die Sprecher-Trennung ist dort *trivial*, weil zwei physisch getrennte Quellen vorliegen. Mehr in Kapitel 3.

### 2.2 STT (Speech-to-Text) — der EU-DSGVO-Knackpunkt

Hier liegt der eigentliche Souveränitäts-Hebel. Latenz unter ~300 ms ist Pflicht, sonst kommt die Karte zu spät.

| API | Herkunft | Latenz (partial/final) | Deutsch | Diarisation | EU-Residency / Retention | Preis (real-time) |
|---|---|---|---|---|---|---|
| **Gladia** | **🇫🇷 Frankreich** | **~100 ms / ~270 ms** | ja, stark | ja (pyannoteAI), bundled | **100 % EU-Residency (vertraglich), Zero-Retention, kein Training auf deinen Audios** | ~$0,75/h |
| Speechmatics | 🇬🇧 UK | <500 ms / <2 s | ja | ja, stark (Kernfeature) | ISO27001/SOC2, on-prem/air-gapped möglich, UK ≠ EU | tiered |
| Deepgram | 🇺🇸 US | <300 ms | ja | ja | US-Cloud | ~$0,60/h |
| AssemblyAI | 🇺🇸 US | streaming (wenige Sprachen) | begrenzt im Streaming | ja (add-on) | US/EU-Zone wählbar | modular |
| OpenAI gpt-4o-transcribe | 🇺🇸 US | gut | ja | nein nativ | US-Cloud | $0,006/min |
| faster-whisper / WhisperX (OSS) | self-host | abhängig | large-v3 gut | pyannote | **du hostest** | GPU-Kosten |

**STT-Empfehlung:** **Gladia.** Klarer Treffer für dich:
- **100 % EU-Datenresidenz** (Frankreich, EU-Recht — *kein* US-CLOUD-Act-Problem, anders als „AWS Frankfurt").
- Zero-Retention + vertraglich kein Modelltraining auf deinen Audios (im DPA prüfbar, nicht nur Marketing).
- **~100 ms Partials / ~270 ms Finals** — schnell genug fürs Overlay.
- Diarisation gebündelt (nutzt pyannoteAI), dazu „Audio-to-LLM" (kann Transkript + strukturierte LLM-Antwort in *einem* Call liefern — spart einen Hop).
- Vermarktet **explizit „Real-Time-Coaching"** als Use Case und hat einen eigenen Meeting-Bot-STT-Leitfaden. Die haben genau dein Szenario im Blick.

Wenn du je on-prem/air-gapped *musst* (z. B. ein Kunde im öffentlichen Sektor verlangt es): **Speechmatics** als Fallback — etwas langsamer, aber on-prem-fähig.

**Diarisation-Detail:** Gladia vergibt Speaker-Labels im *finalen* Transkript (nicht in Echtzeit pro Wort). Für 1:1 egal (Quelle = Sprecher). Für Gruppen liefert der **Bot** ohnehin getrennte Teilnehmer-Kanäle → saubere Echtzeit-Zuordnung. Beides kombiniert = optimal.

### 2.3 Reasoning + Wissensschicht — und warum du KEIN Modell trainierst

Du hattest „trainiertes Modell" gesagt — **mach das nicht.** Fine-Tuning ist hier fast immer der falsche Reflex: teuer, nicht aktualisierbar, Coaching-Konzepte ändern sich. Du willst genau das Muster, auf das ihr bei KOLONIE schon umgestiegen seid: **Wissen als Kontext/MCP-Schicht, nicht in Gewichten.** Die Coaching-Frameworks, Fragetechniken und Methodenbausteine liegen als strukturiertes Wissen (Skill/MCP-Server) vor; das LLM holt sie zur Laufzeit. Fine-Tuning lohnt allenfalls für *Tonalität/Stil*, nie für Wissen.

**EU-LLM-Optionen für die Reasoning-Schicht:**

| Modell/Provider | Herkunft | Souveränität | Deutsch | Anmerkung |
|---|---|---|---|---|
| **Mistral** (Medium 3.5 / Magistral) | **🇫🇷 Paris** | EU-nativ, Mistral Cloud Paris = echte Souveränität; auch Bedrock Frankfurt / Azure EU; Apache-2.0-Modelle self-hostbar | sehr stark (DACH-fokussiert) | **Primärempfehlung.** Du hast den Bedrock-Frankfurt-Guide schon. |
| Aleph Alpha (Pharia) | 🇩🇪 Heidelberg | deutsche Jurisdiktion, on-prem | schlägt Mistral auf dt. Benchmarks, „explainable" | ⚠️ **Cohere (Kanada) hat AA im April 2026 übernommen** — Souveränitäts-Status unklar, vor Langfrist-Bindung prüfen |
| Teuken-7B (OpenGPT-X/Fraunhofer) | 🇪🇺 EU | voll souverän, 24 EU-Sprachen, open-weight | ok | echte Souveränität, aber nicht GPT-Klasse |

**Reasoning-Empfehlung:** **Mistral** als Default. Für maximale Souveränität über **Mistral Cloud (Paris)** statt Bedrock Frankfurt — denn „EU-Region bei US-Anbieter" heißt Residency **ja**, Souveränität **nein** (US-CLOUD-Act greift trotzdem). Für die Praxis kannst du die Calls über deine bestehende **Requesty-DSGVO-Routing**-Schiene schicken und Modelle je Sensibilität routen. Die Wissensschicht baust du als **MCP-Server** (passt in deine KOLONIE-/WERKBANK-Architektur).

### 2.4 Overlay — der semitransparente Layer (dein neuer Kernwunsch)

Genau die Technik, die du beschreibst (semitransparenter, immer-oben-Layer, der unten Antworten einblendet und im Screen-Share **nicht** auftaucht), ist 2025/26 zu einer eigenen Produktkategorie geworden — getrieben von **Cluely** und einer Welle von Open-Source-Klonen.

**Die Technik (gelöst):**
- Fenster: Electron/Tauri `BrowserWindow` mit `transparent`, `frame:false`, `alwaysOnTop`, `skipTaskbar`.
- **Der entscheidende Trick — Screen-Share-Unsichtbarkeit:** Windows `SetWindowDisplayAffinity(handle, WDA_EXCLUDEFROMCAPTURE)`; macOS `NSWindow.sharingType = .none` + Panel-Style + `hasShadow:false`. Damit ist das Overlay **für den Nutzer sichtbar, aber nicht in Zoom/Teams/Meet/OBS-Capture**. Es ist dieselbe Mechanik, die Zoom selbst für Overlays nutzt. (Linux/Wayland ist hier am fragilsten.)

**Open-Source-Vorlagen (nach Eignung für dich):**

| Projekt | Stack | Besonderheit | Lizenz-Hinweis |
|---|---|---|---|
| **Pluely** (`iamsrikanthnani/pluely`) | **Tauri (Rust)** | **~10 MB, <100 ms Start, ~50 MB RAM, cross-platform** (.dmg/.msi/.deb/.rpm/.AppImage), screenshot-proof, BYOK | **Beste technische Basis** — leicht, plattformübergreifend, „muss überall gehen" erfüllt |
| Glass (`pickle-com/glass`) | Electron | screen-share-invisible, Real-Time-Meeting-Assistant | ⚠️ Lizenz-Streit (angeblich aus „cheating-daddy" kopiert) — Lizenz genau prüfen |
| Open-Cluely (`shubhamshnd`) | Electron | **Dual-Source-Capture (System-Audio + Mic)**, AssemblyAI-Streaming, Mobile-Companion | Referenz für die Audio-Capture-Logik |
| OpenCluely (`TechyCSR`) | Electron | Whisper-Halluzinations-Filter, VAD auf natürlichen Pausen | gute Detaillösungen |
| Natively | Electron | <500 ms, Stealth, lokal | „source-available", **nicht-kommerziell** — für Produkt ungeeignet |

**Overlay-Empfehlung:** **Pluely** als Architektur-Vorlage (Tauri = leicht + cross-platform + Rust-Backend passt zu Souveränität). Die **Dual-Source-Audio-Logik** (System-Audio + Mic getrennt) übernimmst du konzeptionell aus **Open-Cluely**. **Lizenzen einzeln prüfen** — viele dieser Repos sind „frei für privat/nicht-kommerziell"; für ein ZUKUNFTSBUND-Produkt brauchst du eine saubere kommerzielle Basis (Pluely tendenziell permissiv, Glass kritisch). → kurz mit Carsten Lexa gegenchecken.

> **Brand-Warnung:** Diese gesamte Kategorie ist „Cheating-Tool"-konnotiert (Interview-/Klausurbetrug). Cluely selbst: 16 Subprozessoren inkl. OpenAI/Grok/Anthropic mit Datenzugriff, **Datenleck mit 83.000 Nutzern** 2025. Das ist exakt das Gegenteil eurer Positionierung — und genau dadurch euer Differenzierungsmerkmal: **EU-souverän, einwilligungsbasiert, transparent = der Anti-Cluely.** Vermarktet das niemals als „unsichtbar für den Gesprächspartner", sondern als „**dein privater Hinweis-Layer**, der beim Screen-Sharing deine internen Notizen nicht an den Klienten leakt". Der Klient hat der KI-Verarbeitung ja zugestimmt — das Overlay versteckt nur *deine* private Assistenz-Ebene, nicht die *Tatsache* der KI-Nutzung.

---

## 3. Architektur-Varianten & Empfehlung

### Variante A — Overlay-native Capture (Empfehlung für 1:1)

Das Overlay greift lokal System-Audio (Gegenüber) + Mic (Coach) getrennt ab → streamt direkt zu Gladia → Reasoning → blendet im selben Overlay ein. **Kein Bot.**

- **Pro:** niedrigste Latenz (ein Hop weniger), keine Bot-Infrastruktur/-Kosten, kein „Bot tritt bei"-Reibung, Sprecher-Trennung trivial (2 Quellen), „kein lokales Processing" erfüllt (Audio-*Capture* ist kein Processing — STT/LLM laufen in der Cloud).
- **Contra:** System-Audio-Capture ist OS-spezifisch (macOS braucht ScreenCaptureKit/Screen-Recording-Permission; Windows WASAPI-Loopback; Linux PipeWire) — die Cluely-Klone lösen das aber bereits, also beherrschbar.

### Variante B — Cloud-Bot-Capture (für Gruppen / sichtbaren Consent)

Vexa/Recall-Bot tritt bei → Cloud-STT → Reasoning → pusht an schlankes Overlay (WebSocket).

- **Pro:** plattformunabhängig über Meeting-Link, saubere Pro-Teilnehmer-Diarisation, **sichtbarer Bot = sauberes Einwilligungsartefakt** (gut für § 201 StGB), Capture-Probleme komplett in der Cloud.
- **Contra:** ein Hop mehr (Audio→Bot→STT), Bot-Kosten/Stunde, manche empfinden Bot als intrusiv, Overlay existiert trotzdem lokal.

### Empfehlung

**Variante A als Primärweg** (Coaching ist überwiegend 1:1, Latenz + „überall" sprechen dafür), **Variante B als zuschaltbare Option** für Gruppen-Settings oder wenn ein Kunde einen sichtbaren Consent-Bot bevorzugt. Beide teilen sich Schicht 2–4 — du baust das Reasoning + Overlay **einmal**, die Capture ist austauschbar. Genau das macht es zum **Modul**.

---

## 4. Latenzbudget (ehrliche Zahlen)

Vom Ende der Äußerung des Gegenübers bis zur Karte im Overlay:

| Schritt | Zeit |
|---|---|
| Audio-Capture (lokal) | ~vernachlässigbar |
| Netz → Gladia (EU) | ~20–50 ms |
| Gladia Final-Transkript | ~270 ms |
| Trigger-Router (Karte ja/nein?) | ~50–150 ms (kleines schnelles Modell/Regeln) |
| Mistral erste Tokens (Streaming) | ~500 ms – 1,5 s |
| **Karte beginnt sichtbar zu werden** | **~1–2 s nach Sprechpause** |

Das ist für einen Coach **nutzbar** — er hat ohnehin natürliche Denkpausen. Entscheidend: **streamen** (Karte baut sich auf, nicht „alles auf einmal nach 4 s") und **nur bei Trigger** feuern, nicht auf jeder Äußerung. Volle 4-6-s-Antworten auf jeden Satz wären Gesprächs-Tod.

---

## 5. Konkurrenz für das Gesamtprodukt & Marktlücke

Kein Tool deckt deinen exakten Fall ab. Die nächstliegenden Kategorien:

**A) Sales-Coaching-Copiloten (funktional am nächsten):** Gong, Chorus, **Balto**, **Salesken**, Avoma, Revenue.io („Moments"), Dialpad (RTA-Cards), **Jiminny** (UK, GDPR-fokussiert). Diese machen *exakt* „Echtzeit-Karte mit Antwortvorschlag auf Screen". **Aber:** durchweg *vertrieblich* (nicht Coaching), meist *US-Cloud*, *geschlossen*, *nicht als Modul* einbettbar. → **UX-Muster studieren** (Trigger-Cards statt Dauerbeschallung haben sie gelöst), aber falsche Domäne + Souveränität.

**B) Meeting-Assistenten (async, nicht Echtzeit-Copilot):** Otter, Fireflies, Fathom, **tl;dv (München, EU)**, Read.ai. Liefern Protokoll/Zusammenfassung *nach* dem Call — nicht den Live-Layer.

**C) Overlay-„AI-Assistants" (richtige UX, falsche Werte):** Cluely (geschlossen, US, Datenleck), Glass/Pluely/Natively (OSS, aber Cheating-Fokus + lokale LLMs). Richtige Form, aber keine Coaching-Wissensschicht, kein EU-Compliance-Anspruch.

### Die Lücke (= dein Produkt)

```
                    EU-souverän/DSGVO
                          ▲
                          │        ★ ZUKUNFTSBUND
            Jiminny ──────│         Coaching-Copilot
            (UK, Sales)   │        (hier ist niemand)
                          │
   Sales ◀───────────────┼───────────────▶ Coaching/
   (Gong, Balto)         │                 Methodik
                          │
            Cluely/Glass ─│
            (US, Overlay) │
                          ▼
                    US-Cloud/Closed
```

Niemand kombiniert **EU-souverän + Echtzeit-Overlay + Coaching-Methodik + modular**. Das ist verteidigbares Whitespace.

---

## 6. Buy vs. Build vs. Modul

| Schicht | Entscheidung | Konkret |
|---|---|---|
| Capture | **Buy/OSS** | Vexa (OSS) für Bot-Variante; lokale Capture-Logik aus Open-Cluely übernehmen |
| STT + Diarisation | **Buy (EU-API)** | Gladia |
| Reasoning-LLM | **Buy (EU-API)** | Mistral (Paris), via Requesty-Routing |
| Wissensschicht | **Build** | MCP-Server mit Coaching-Konzepten (dein IP) |
| Trigger-/Reasoning-Logik | **Build** | dein IP — *wann* welche Karte, in welchem methodischen Stil |
| Overlay-UI | **Build (auf OSS-Basis)** | Tauri, Vorlage Pluely |

**Faustregel:** Commodity kaufen (STT/LLM/Capture sind ausgereift und billig), **IP selbst bauen** (Wissensschicht + Trigger-Logik + Overlay-UX). Niemals STT oder Diarisation selbst erfinden.

---

## 7. Recht, DSGVO & Ethik — das ist kein Häkchen, das ist Strafrecht

**Wichtigster Punkt, den fast alle übersehen:**

### § 201 StGB — Verletzung der Vertraulichkeit des Wortes
Das Aufzeichnen des **nicht-öffentlich gesprochenen Wortes ohne Einwilligung ist eine Straftat** (bis 3 Jahre Freiheitsstrafe) — **nicht** bloß ein DSGVO-Bußgeld. Deine Logik „Gegenüber stimmt zu, bekommt dafür das Protokoll mit Diarisation" ist deshalb nicht nur fair, sondern **rechtlich zwingend**. Einwilligung muss **explizit, dokumentiert und vor Aufnahme** erfolgen (hörbar zu Beginn + idealerweise schriftlich/per Klick).

### DSGVO
- **Art. 6** (Rechtsgrundlage) + **sehr wahrscheinlich Art. 9** — Coaching berührt psychische/gesundheitliche Themen → **besondere Kategorie personenbezogener Daten** → höhere Hürden (ausdrückliche Einwilligung, DSFA).
- **Art. 28 DPA** mit jedem Auftragsverarbeiter (Gladia, Mistral, ggf. Bot-Provider) — bei EU-Anbietern sauber machbar.
- **DSFA (Art. 35)** ist hier faktisch Pflicht (systematische Verarbeitung sensibler Daten in Echtzeit).
- **CLOUD-Act-Falle:** „EU-Region bei US-Anbieter" (z. B. AWS Frankfurt) = Residency ja, Souveränität nein. Für euren Markenkern → **EU-eigene Anbieter** (Gladia FR, Mistral Cloud Paris) bevorzugen.

### EU AI Act
- Wenn das Tool **emotionale Zustände** ableitet („Gegenüber wirkt abwehrend/unsicher") → das ist **Emotionserkennung**. Im **Arbeits- und Bildungskontext verboten** (Art. 5). Coaching liegt vermutlich *außerhalb* — aber das gehört **geprüft, nicht angenommen**. Sicherer Default: auf *inhaltliche* Ableitungen fokussieren („nennt 3× Zeitdruck"), nicht auf Emotions-Scoring.
- **Transparenzpflicht:** Betroffene müssen wissen, dass sie mit/über ein KI-System interagieren — deckt sich mit der Einwilligung.

### Ethik / Brand
Die „screen-share-unsichtbar"-Funktion ist **dual-use**. Die einzige Grenze zwischen legitimem Coaching-Tool und Cluely-artigem Betrug ist die **Einwilligung**. Halte das sauber:
- Klient stimmt **KI-Verarbeitung** zu (transparent).
- Das Overlay versteckt nur den **privaten Hinweis-Layer des Coaches** beim Screen-Sharing — nicht die Tatsache der KI-Nutzung.
- Vermarktung „Mach's doch gleich richtig": **transparent, EU-souverän, einwilligungsbasiert** — explizit als Gegenentwurf zu Cluely.

→ **Vor erstem Echtbetrieb zwingend über Carsten Lexa.** Kein Spielraum. (Einwilligungstext, DSFA, AI-Act-Einordnung, Lizenz-Check der OSS-Basis.)

---

## 8. Bauplan in Phasen

**Phase 0 — Recht & Setup (vor Code)**
Lexa: Einwilligungstext + DSFA + AI-Act-Einordnung + OSS-Lizenz-Check. DPAs mit Gladia + Mistral. Entscheidung Mistral Cloud Paris vs. Bedrock Frankfurt.

**Phase 1 — Async-MVP (geringes Risiko, sofortiger Nutzen)**
Protokoll + Diarisation + strukturierte Nachbereitung. Capture (Vexa oder lokal) → Gladia → Mistral-Zusammenfassung. **Das ist der sichere, einwilligungsfreundliche, sofort wertstiftende Teil** — und liefert dem Gegenüber den versprochenen Vorteil (Protokoll). Hier kein Overlay nötig.

**Phase 2 — Live-Overlay (die Ausbaustufe)**
Tauri-Overlay (Basis Pluely) + lokale Dual-Source-Capture + Gladia-Streaming + Trigger-Router + Mistral-Reasoning + Coaching-MCP-Wissensschicht. Screen-Share-Unsichtbarkeit. Streaming-Karten, nur bei Trigger.

**Phase 3 — Modularisierung**
Schicht 2–4 als sauber gekapseltes Modul (Transkript-Event-Bus als Schnittstelle), das du in andere Lösungen einbettest (oder als ZUKUNFTSBUND-Produkt verkaufst). Capture-Adapter austauschbar (lokal ↔ Bot).

---

## 9. Grobe Kostenschätzung (laufend, pro Stunde Gespräch)

| Posten | Kosten/h |
|---|---|
| STT (Gladia real-time + Diarisation) | ~$0,75 |
| Capture-Bot (nur Variante B, Vexa) | ~$0,30 (entfällt bei Variante A) |
| Reasoning (Mistral, nur bei Triggern, gestreamt) | ~$0,10–0,50 (stark nutzungsabhängig) |
| **Summe Variante A (lokal)** | **~$0,85–1,25/h** |
| **Summe Variante B (Bot)** | **~$1,15–1,55/h** |

Plus einmalig: Entwicklung Overlay + Wissensschicht + Trigger-Logik. Modellkosten lassen sich über Haiku-/kleine-Modell-Routing für den Trigger-Router und teurere Modelle nur für die eigentliche Antwort drücken (Model-Efficiency-Prinzip).

---

## 10. Netto-Empfehlung

1. **Bauen, aber nur das IP** — Wissensschicht (MCP) + Trigger-Logik + Overlay. Commodity (STT/LLM/Capture) als EU-API einkaufen.
2. **EU-Kette:** Gladia (STT, FR) + Mistral (Reasoning, Paris) + Vexa (Capture-OSS, falls Bot) + Tauri-Overlay (Basis Pluely). Routing über deine Requesty-Schiene.
3. **Variante A (lokale Capture)** als Primärweg fürs 1:1-Coaching, **Variante B (Bot)** zuschaltbar für Gruppen.
4. **Phase 1 zuerst** (Async-Protokoll) — geringes Risiko, sofortiger Nutzen, einfache Einwilligung. Live-Overlay als Phase 2.
5. **Recht vor Code** — § 201 StGB + Art. 9 + AI Act über Lexa. Das ist der Showstopper, nicht die Technik.
6. **Positionierung als Anti-Cluely:** transparent, EU-souverän, einwilligungsbasiert. Das ist gleichzeitig euer Differenzierungsmerkmal und eure rechtliche Absicherung.

**Brutal ehrlich:** Der Live-Vorschlags-Layer ist das Schaufenster — aber rechtlich am heikelsten und für die Coaching-Qualität am fragwürdigsten (ein Coach, der aufs Overlay schielt, ist nicht mehr präsent beim Klienten). Der **sichere, sofort wertstiftende, einwilligungsfreundliche** Teil ist das Protokoll mit Diarisation. Deshalb Phase 1 zuerst — und das Overlay als bewusste, gut gebaute Ausbaustufe obendrauf.

---

### Anhang — Quellen-Kurzliste (Stand 06/2026)
Recall.ai · Vexa (vexa.ai, Apache 2.0) · Attendee.dev · MeetStream/Skribby/MeetingBaaS-Vergleiche · Gladia (gladia.io, EU-Residency, Solaria-1, Real-Time-Coaching-Use-Case) · Speechmatics · Mistral (innfactory/Mistral, Paris + Bedrock FFM) · Aleph Alpha (Cohere-Übernahme 04/2026) · Teuken-7B (OpenGPT-X) · Cluely + Undetectability-Doku · Glass (pickle-com) · Pluely (Tauri) · Open-Cluely (Dual-Source-Capture) · `SetWindowDisplayAffinity`/`WDA_EXCLUDEFROMCAPTURE` (Screen-Share-Unsichtbarkeit) · § 201 StGB · EU AI Act Art. 5 (Emotionserkennung).
