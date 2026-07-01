# packages/shared — Geteilte Typen und Schemas

Single Source of Truth für die Datenstrukturen über die Schicht-Grenzen hinweg: TranscriptEvent, BusEvent, Card, SessionContext, ProviderCapabilities.

## Was hier hineingehört

- `src/` — TypeScript-Typen (für Web und Overlay) und JSON-Schemas. Das Backend spiegelt dieselben Strukturen in Python (ports/types.py).

## Zweck

Konsistenz zwischen Backend, Web und Overlay; verhindert Drift der Event- und Karten-Formate. Der Event-Bus (BusEvent) ist hier definiert und ist die Modul-Schnittstelle für Phase 3.
