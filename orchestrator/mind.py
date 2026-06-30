#!/usr/bin/env python3
"""kiln — persistente Minds (deterministisch).

Reviewer/Architekt-„Minds" behalten Historie über Chunks; Builder werden frisch gespawnt
(`is_persistent` = False -> kein Mind injizieren). Vor dem Spawn einer persistenten Rolle wird
`context(role)` in den Prompt gegeben; nach dem Lauf `append(role, erkenntnis)`.

State: <minds_dir>/<role>.json (Default `.werkbank/minds/`). Kein Clock nötig (Sequenz statt Zeit).

CLI:  mind.py append <role> "<eintrag>" [minds_dir]
      mind.py context <role> [limit] [minds_dir]
"""
import json
import os
import sys

PERSISTENT_ROLES = {"reviewer", "architect", "judge", "privacy-analyst", "tribunal", "qa"}
_DEFAULT_DIR = os.path.join(".werkbank", "minds")


def is_persistent(role):
    return (role or "").strip().lower() in PERSISTENT_ROLES


def _path(minds_dir, role):
    safe = "".join(c for c in (role or "").lower() if c.isalnum() or c in "-_") or "role"
    return os.path.join(minds_dir, safe + ".json")


def load(minds_dir, role):
    try:
        with open(_path(minds_dir, role), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def append(minds_dir, role, entry):
    items = load(minds_dir, role)
    items.append({"seq": len(items) + 1, "entry": entry})
    os.makedirs(minds_dir, exist_ok=True)
    with open(_path(minds_dir, role), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return len(items)


def context(minds_dir, role, limit=10):
    items = load(minds_dir, role)[-int(limit):]
    if not items:
        return ""
    head = "## Mind „%s" % role + "\" (Historie aus früheren Chunks)\n"
    return head + "\n".join("- %s" % it["entry"] for it in items)


def main(argv):
    if len(argv) >= 3 and argv[0] == "append":
        role, entry = argv[1], argv[2]
        minds_dir = argv[3] if len(argv) > 3 else _DEFAULT_DIR
        print("seq=%d" % append(minds_dir, role, entry))
        return 0
    if len(argv) >= 2 and argv[0] == "context":
        role = argv[1]
        limit = argv[2] if len(argv) > 2 and argv[2].isdigit() else "10"
        minds_dir = argv[3] if len(argv) > 3 else (argv[2] if len(argv) > 2 and not argv[2].isdigit() else _DEFAULT_DIR)
        print(context(minds_dir, role, int(limit)))
        return 0
    print("usage: mind.py append <role> <entry> [dir] | context <role> [limit] [dir]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
