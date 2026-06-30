#!/usr/bin/env python3
"""Budget / Kill-Switch (deterministisch).

`check(spent, cap, kill)` -> ok | warn | kill. 0 = Limit nicht gesetzt (löst nie aus).
State in `.werkbank/budget.json` {spent_eur, period_cap_eur, kill_switch_eur}.
Ehrlich: der Spend wird vom Orchestrator eingespeist (`budget.py add <eur>`) — WERKBANK metert
nicht automatisch. Der Kill-Switch stoppt den Ralph-Loop (HALT) bei Erreichen.

CLI:  budget.py check [state.json]   -> Exit 0 (ok/warn) / 4 (kill)
      budget.py add <eur> [state.json]
"""
import json
import os
import sys

_DEFAULT = {"spent_eur": 0, "period_cap_eur": 0, "kill_switch_eur": 0}


def check(spent, cap, kill):
    if kill and kill > 0 and spent >= kill:
        return ("kill", "Kill-Switch erreicht: %.2f >= %.2f EUR" % (spent, kill))
    if cap and cap > 0 and spent >= cap:
        return ("warn", "Budget-Cap erreicht: %.2f >= %.2f EUR" % (spent, cap))
    return ("ok", "im Budget (%.2f EUR)" % spent)


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return {k: d.get(k, _DEFAULT[k]) for k in _DEFAULT}
    except (OSError, ValueError):
        return dict(_DEFAULT)


def save_state(path, state):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def add_spend(path, eur):
    st = load_state(path)
    st["spent_eur"] = round(st["spent_eur"] + float(eur), 4)
    save_state(path, st)
    return st["spent_eur"]


def main(argv):
    if not argv:
        print("usage: budget.py check|add ...", file=sys.stderr)
        return 2
    cmd = argv[0]
    if cmd == "check":
        path = argv[1] if len(argv) > 1 else os.path.join(".werkbank", "budget.json")
        st = load_state(path)
        action, reason = check(st["spent_eur"], st["period_cap_eur"], st["kill_switch_eur"])
        print("%s\t%s" % (action, reason))
        return 4 if action == "kill" else 0
    if cmd == "add":
        eur = argv[1]
        path = argv[2] if len(argv) > 2 else os.path.join(".werkbank", "budget.json")
        print("spent_eur=%.2f" % add_spend(path, eur))
        return 0
    print("unbekannter Befehl: %s" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
