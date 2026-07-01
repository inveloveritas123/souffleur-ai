# THIRD-COUNTRY-TRANSFERS — Souffleur AI

Bewertung von Drittlandübermittlungen nach Kapitel V DSGVO.

## Ergebnis

Drittlandtransfer: nein. Alle Auftragsverarbeiter (Mistral SAS Paris, optional Gladia Frankreich) sitzen in der EU. Alle Modellaufrufe gehen über die EU-Basis-URL api.mistral.ai. Es findet keine Übermittlung in ein Land außerhalb des Europäischen Wirtschaftsraums statt.

## Begründung der EU-Souveränität

Die Architektur vermeidet bewusst die Falle Region-bei-Nicht-EU-Anbieter. EU-Region bei einem nicht-europäischen Cloud-Anbieter bedeutet Residency ja, Souveränität nein, da ausländische Zugriffsgesetze greifen können. Souffleur AI setzt deshalb auf europäische Anbieter mit europäischer Jurisdiktion.

## Kontrollen

- Gate E1 verhindert die Referenzierung eines Non-EU-Endpunkts oder einer Non-EU-Region in Code und Konfiguration.
- Die Verarbeiter-Verträge sichern EU-Region zu.
- Bei künftiger Hinzunahme eines Dienstes außerhalb des Europäischen Wirtschaftsraums wäre vor Aktivierung eine Übermittlungs-Folgenabschätzung mit geeigneten Garantien (Art. 46) erforderlich. Dies ist derzeit nicht vorgesehen.
