#!/usr/bin/env python3
"""WERKBANK Tier-Router — Policy-Engine für die Modellwahl je Subagent (deterministisch).

Bildet einen Aufgabentyp (z. B. "doku", "review", "impl") auf ein Tier/Modell ab. Liefert NUR
die Policy; das tatsächliche Setzen des Modells beim Spawnen eines Subagenten muss der
Orchestrator tun (in Claude Code: `model=` am Agent-Aufruf bzw. `model:` im Agent-Frontmatter).
Python kann das Modell nicht erzwingen — es entscheidet, was gesetzt WERDEN soll.

CLI:
  python3 orchestrator/tier_router.py review          -> Modell für ein Label
  python3 orchestrator/tier_router.py --table         -> ganze Routing-Tabelle
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_POLICY_PATH = os.path.join(HERE, "werkbank.tiers.json")
_TIER_RANK = {"haiku": 1, "sonnet": 2, "opus": 3}

# Eingebaute Defaults (greifen, falls die Policy-Datei fehlt).
_BUILTIN = {
    "tiers": {"haiku": "haiku", "sonnet": "sonnet", "opus": "opus"},
    "routing": {"doku": "haiku", "summary": "haiku", "impl": "sonnet", "test": "sonnet",
                "plan": "opus", "review": "opus", "security": "opus", "privacy": "opus"},
    "default": "sonnet",
    "confirm_tier_from": "opus",
}


def load_policy(path=None):
    path = path or DEFAULT_POLICY_PATH
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            # verschachtelt mergen: partielle Datei ergänzt die Defaults, ersetzt sie nicht.
            return {
                "tiers": {**_BUILTIN["tiers"], **data.get("tiers", {})},
                "routing": {**_BUILTIN["routing"], **data.get("routing", {})},
                "default": data.get("default", _BUILTIN["default"]),
                "confirm_tier_from": data.get("confirm_tier_from", _BUILTIN["confirm_tier_from"]),
            }
        except (ValueError, OSError):
            pass
    return dict(_BUILTIN)


def route(task_type, policy=None):
    """Aufgabentyp -> {task, tier, model, confirm}. Unbekannt -> default-Tier."""
    p = policy or load_policy()
    tier = p["routing"].get((task_type or "").strip().lower(), p["default"])
    model = p["tiers"].get(tier, tier)
    confirm_from = p.get("confirm_tier_from")
    confirm = bool(confirm_from) and _TIER_RANK.get(tier, 0) >= _TIER_RANK.get(confirm_from, 99)
    return {"task": task_type, "tier": tier, "model": model, "confirm": confirm}


def table(policy=None):
    p = policy or load_policy()
    return [route(t, p) for t in sorted(p["routing"])]


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "--table":
        print("%-14s %-8s %-8s %s" % ("Aufgabe", "Tier", "Modell", "Bestätigen?"))
        for r in table():
            print("%-14s %-8s %-8s %s" % (r["task"], r["tier"], r["model"], "ja" if r["confirm"] else "nein"))
        return 0
    r = route(argv[0])
    print(r["model"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
