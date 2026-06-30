#!/usr/bin/env python3
"""Auto-Labeler — Aufgabentext -> Label -> Modell (schließt Issue #5).

Macht die Modellwahl automatisch, statt Konvention: Der Orchestrator ruft `route(task)` und erhält
das Tier-passende Modell, ohne manuell zu labeln. `lint_agent_dir()` flaggt Agent-Definitionen ohne
`model:`-Frontmatter (damit kein Subagent unpinned auf dem teuren Default landet).

Hinweis (ehrlich): Ein Skript kann den Agent-Spawn in Claude Code nicht *erzwingen* — es entfernt die
manuelle Hürde und der Lint fängt unpinned Agent-Defs. Volle Erzwingung = `model:`-Frontmatter je Agent.

CLI:  autolabel.py "<aufgabentext>"   -> "label\tmodel"
      autolabel.py --lint <agents-dir>
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tier_router  # noqa: E402

# Reihenfolge = Priorität (spezifisch vor generisch).
RULES = [
    ("review",   ["review", "prüf", "pruef", "audit", "adversarial", "vier-augen", "tribunal", "begutacht"]),
    ("security", ["security", "secret", "exploit", "pentest", "schwachstelle", "sicherheits"]),
    ("privacy",  ["dsgvo", "datenschutz", "privacy", "pii", "dpia", "dsfa", "einwilligung"]),
    ("plan",     ["architekt", "design", "plan", "konzept", "prd", "story", "brief"]),
    ("test",     ["test", "unittest", "pytest", "coverage"]),
    ("doku",     ["doku", "dokument", "readme", "zusammenfass", "zusammen", "fasse", "summary", "changelog", "kommentar"]),
    ("impl",     ["implement", "baue", "code", "fix", "refactor", "funktion", "feature"]),
]
DEFAULT = "impl"
_FRONTMATTER_MODEL = re.compile(r"^model:\s*\S+", re.M)


def autolabel(task_text):
    t = (task_text or "").lower()
    for label, kws in RULES:
        if any(k in t for k in kws):
            return label
    return DEFAULT


def route(task_text):
    label = autolabel(task_text)
    r = tier_router.route(label)
    r["label"] = label
    return r


def lint_agent_dir(agents_dir):
    missing = []
    if not os.path.isdir(agents_dir):
        return missing
    for name in sorted(os.listdir(agents_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(agents_dir, name), encoding="utf-8", errors="replace") as f:
            if not _FRONTMATTER_MODEL.search(f.read()):
                missing.append(name)
    return missing


def main(argv):
    if argv and argv[0] == "--lint":
        d = argv[1] if len(argv) > 1 else "agents"
        miss = lint_agent_dir(d)
        for m in miss:
            print("ohne model:-Frontmatter -> %s" % m)
        return 1 if miss else 0
    if not argv:
        print("usage: autolabel.py \"<task>\" | --lint <dir>", file=sys.stderr)
        return 2
    r = route(" ".join(argv))
    print("%s\t%s" % (r["label"], r["model"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
