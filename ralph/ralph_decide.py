#!/usr/bin/env python3
"""Ralph-Loop — Entscheidungs-Engine (deterministisch, kein LLM).

EINE Quelle der Wahrheit für „weitermachen / fertig / anhalten", genutzt vom Bash-Motor
(ralph-loop.sh) UND vom Stop-Hook (stop_hook.py).

Regeln (Reihenfolge zählt):
1. Drift-Pausegate: mehr rote Block-Gates als in der Vorrunde -> HALT (anhalten, Ursache nennen).
2. Fertig: alle Block-Gates grün UND completion-promise vorhanden -> STOP.
3. Sicherheitsnetz: iteration >= max_iterations -> HALT (eskalieren).
4. Sonst -> CONTINUE (mit Grund, was noch fehlt).

CLI:  ralph_decide.py <gates_ok 0|1> <promise 0|1> <iteration> <max_iter> <prev_red> <cur_red>
      -> druckt "ACTION\tREASON" (ACTION in stop|continue|halt), Exit 0.
"""
import sys


def decide(gates_ok, promise, iteration, max_iter, prev_red=-1, cur_red=0):
    if prev_red >= 0 and cur_red > prev_red:
        return ("halt", "Drift-Pausegate: rote Block-Gates gestiegen (%d -> %d) — anhalten, Ursache nennen"
                % (prev_red, cur_red))
    if gates_ok and promise:
        return ("stop", "GRUEN + completion-promise — fertig")
    if iteration >= max_iter:
        return ("halt", "max-iterations (%d) erreicht ohne GRUEN+promise — eskalieren" % max_iter)
    miss = []
    if not gates_ok:
        miss.append("Block-Gates rot")
    if not promise:
        miss.append("promise fehlt")
    return ("continue", "weiterarbeiten: %s" % (", ".join(miss) or "unklar"))


def main(argv):
    if len(argv) < 4:
        print("halt\tzu wenige Argumente")
        return 2
    gates_ok = argv[0] == "1"
    promise = argv[1] == "1"
    iteration = int(argv[2])
    max_iter = int(argv[3])
    prev_red = int(argv[4]) if len(argv) > 4 else -1
    cur_red = int(argv[5]) if len(argv) > 5 else 0
    action, reason = decide(gates_ok, promise, iteration, max_iter, prev_red, cur_red)
    print("%s\t%s" % (action, reason))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
