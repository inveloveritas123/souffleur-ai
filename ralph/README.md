# Ralph-Loop — Verification-first-Autonomie (Blueprint §2)

Iteriert „Worker → Gates → completion-promise → Entscheidung", bis **alle Block-Gates grün sind
UND der promise `<promise>GRUEN</promise>` erscheint** — oder bis `--max-iterations` greift bzw.
das **Drift-Pausegate** anhält (mehr rote Gates als in der Vorrunde).

## Eine Entscheidungs-Engine, zwei Motoren
- `ralph_decide.py` — die deterministische Logik (fertig / weiter / anhalten). EINE Quelle der Wahrheit, getestet.
- `ralph-loop.sh` — **Fresh-Context-Motor (empfohlen, Blueprint-bevorzugt):** ruft je Runde einen
  Worker mit **frischem Kontext** auf und re-invoziert bis fertig.
- `stop_hook.py` — **In-Session-Variante:** Claude-Code-Stop-Hook, der verfrühtes Stoppen verhindert.

## Fresh-Context-Motor (vollautonom)
```bash
ralph/ralph-loop.sh \
  --build-cmd 'claude -p "Arbeite die oberste BACKLOG-Story ab; gib bei fertig <promise>GRUEN</promise> aus."' \
  --target . --max-iterations 15
```
Der `--build-cmd` ist der Worker je Runde (frischer Kontext, wenn `claude -p ...`). Er MUSS bei
„fertig" den promise-Marker ausgeben. Exit: `0` fertig · `3` angehalten (Drift/max-iter) · `2` Fehler.

## In-Session-Stop-Hook (opt-in)
`settings.stop-hook.json` in `.claude/settings.json` mergen (oder `werkbank-init.sh --ralph-hook`).
Der Hook blockt das Stoppen, solange Gates rot sind oder der promise fehlt; bei Drift/max-iter
erlaubt er das Stoppen und **eskaliert an den Menschen**.

## Ehrliche Grenze
Ein Stop-Hook `block` **pausiert** verlässlich, **re-invoziert** den Agenten im interaktiven Modus
aber nicht garantiert von selbst (siehe Claude-Code-Hooks-Doku). Für **vollautonome** Läufe ist der
**Fresh-Context-Bash-Motor** der robuste Weg — genau das sagt der Blueprint.

## Tests
`python3 -m unittest discover -s gates/checks/tests -p "test_ralph.py"`
(Engine + Bash-Motor end-to-end + Stop-Hook.)
