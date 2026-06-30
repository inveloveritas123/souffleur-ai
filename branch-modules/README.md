# Branchen-Regelpakete (branch-modules)

Kritische Branchen haben eigene Pflichten, die über DSGVO hinausgehen — z. B. **BaFin/MaRisk**
(Finanz), **HOAI** (Bau), **MDR/Risikomanagement** (Medizin), **KRITIS** (kritische Infrastruktur),
**Geodaten-Lizenzen** (GIS), **Firmware-Signatur** (IoT). WERKBANK verankert sie als **harte Gates**.

## Prinzip (wie DSGVO: erzwingen, nicht halluzinieren)
WERKBANK **erzwingt**, dass die branchenspezifischen Pflicht-Artefakte vorhanden sind (**Gate K1**)
und dass die **fachliche Abnahme durch einen Menschen** vorliegt (**Gate K2**). Die fachliche
**Substanz** (ist die MaRisk-Abbildung korrekt? die HOAI-Berechnung?) liefert der **Domänen-/
Compliance-Experte** — genau wie der DSB die materielle DSGVO-Würdigung. WERKBANK erfindet kein
Fachrecht; es macht es **auditierbar und unumgehbar**.

## Aktivieren
- Pro Projekt: `--branch <name>` oder eine Zeile in `.werkbank/branch.txt` (z. B. `finanzen`).
- Ein passendes Profil (oder `produktiv`) macht **K1/K2 zur Pflicht** → kein Grün ohne Branchenregeln.

## Ein Regelpaket anlegen
`branch-modules/<name>/rules.yaml`:
```yaml
name: medizin
desc: "Medizinprodukt — MDR/Risikomanagement"
required_artefacts: [RISIKOMANAGEMENT.md, MDR-MAPPING.md, GEBRAUCHSANWEISUNG.md]
required_signoff: fachaufsicht     # Abschnitt in docs/produktivfreigabe/FREIGABE.yaml
```
- **K1** prüft, dass alle `required_artefacts` im Projekt vorhanden sind.
- **K2** prüft, dass der `required_signoff`-Abschnitt in `FREIGABE.yaml` signiert erteilt ist
  (`freigegeben: true` + `von` + `datum`) — vom Fach-/Compliance-Verantwortlichen.

Beispiel mitgeliefert: **`finanzen/`** (BaFin/Audit-Trail). Weitere Pakete entstehen mit dem
jeweiligen Domänen-Experten — WERKBANK liefert den Rahmen, nicht das Fachurteil.
