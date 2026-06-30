# Workflow 04 — Übergeben

> Übergabe-Bündel: Spec + Architektur + Tests + Doku + Audit-Log. Kein Selbst-Merge — immer PR.

## Ablauf
1. Nur wenn Done-Tor erfüllt (Score ≥ 85, alle Block-Gates grün, keine Regression).
2. **Deployment-Validierung (I3, Argus-Stil):** kritische User-Flows aus der SPEC gegen die App prüfen —
   **alle müssen bestehen**:
   ```bash
   deploy/deploy_validate.sh \
     --flow 'buchen=claude -p "Validiere <Flow> gegen die App; letzte Zeile VERDICT: pass|fail"' \
     --flow 'stornieren=...'
   ```
3. Bündel: `SPEC.md`, `ARCHITECTURE.md`, Test-Artefakte, `GATE-REPORT.md`, Audit-Log, CHANGELOG-Eintrag.
4. `BACKLOG.md`-Aufgabe auf `[x]`. `.werkbank/STATE.md` + `.werkbank/BENCHMARK.md` aktuell.
5. `git push origin werkbank-build` → **PR gegen `main`** (Mensch merged).

## Sicherung
- Kein Push bei rotem Block-Gate. Kein Selbst-Merge. Rollback bei Regression.
- Geltung beachten: intern, ohne echte Kundendaten (siehe `docs/produktivfreigabe/`).
