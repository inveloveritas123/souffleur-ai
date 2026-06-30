#!/usr/bin/env python3
"""Ralph-Loop — Claude-Code Stop-Hook (In-Session-Variante).

Liest den Stop-Event von stdin, prüft completion-promise (in der letzten Assistant-Nachricht)
+ Gates, entscheidet via ralph_decide. CONTINUE -> blockt das Stoppen und gibt den Grund zurück;
STOP/HALT -> erlaubt das Stoppen (HALT eskaliert an den Menschen). Iterations-Cap in .werkbank/ralph.json.

Hinweis (ehrlich): Der Blueprint bevorzugt den Fresh-Context-Bash-Motor (ralph-loop.sh). Dieser Hook
verhindert verlässlich verfrühtes Stoppen; die Re-Invokation im interaktiven Modus kann je nach
Setup einen Anstoß brauchen — für vollautonome Läufe ralph-loop.sh nutzen.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ralph_decide import decide  # noqa: E402

PROMISE = os.environ.get("RALPH_PROMISE", "<promise>GRUEN</promise>")
MAX_ITER = int(os.environ.get("RALPH_MAX_ITER", "15"))


def _last_assistant_text(data):
    msg = data.get("assistant_message")
    if msg:
        return msg
    tp = data.get("transcript_path")
    if tp and os.path.isfile(tp):
        try:
            with open(tp, encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("type") == "assistant_message":
                    return ev.get("text") or ev.get("content") or ""
        except OSError:
            pass
    return ""


def _gates(cwd):
    report = os.path.join(cwd, "GATE-REPORT.md")
    runner = os.path.join(HERE, "..", "gates", "runner.py")
    cmd = [sys.executable, runner, "--target", cwd, "--report", report, "--ci"]
    if os.environ.get("WERKBANK_PROFILE"):
        cmd += ["--profile", os.environ["WERKBANK_PROFILE"]]
    if os.environ.get("WERKBANK_PFLICHTENHEFT"):
        cmd += ["--pflichtenheft", os.environ["WERKBANK_PFLICHTENHEFT"]]
    try:
        rc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600).returncode
    except (subprocess.SubprocessError, OSError):
        return 0, 99
    red = 0
    try:
        with open(report, encoding="utf-8") as f:
            for ln in f:
                if "Pflicht-Gates ohne PASS:" in ln:
                    red = int("".join(c for c in ln if c.isdigit()) or "0")
                    break
    except OSError:
        pass
    return (1 if rc == 0 else 0), red


def _state(cwd):
    p = os.path.join(cwd, ".werkbank", "ralph.json")
    try:
        with open(p, encoding="utf-8") as f:
            return p, json.load(f)
    except (OSError, ValueError):
        return p, {"iteration": 0, "prev_red": -1}


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0  # nichts zu tun -> Stop erlauben
    cwd = data.get("cwd") or os.getcwd()
    promise = 1 if PROMISE in _last_assistant_text(data) else 0
    gates_ok, cur_red = _gates(cwd)
    path, st = _state(cwd)
    iteration = int(st.get("iteration", 0)) + 1
    prev_red = int(st.get("prev_red", -1))

    action, reason = decide(gates_ok, promise, iteration, MAX_ITER, prev_red, cur_red)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_state = {"iteration": 0, "prev_red": -1} if action != "continue" else {"iteration": iteration, "prev_red": cur_red}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new_state, f)
    except OSError:
        pass

    if action == "continue":
        json.dump({"decision": "block", "reason": "[Ralph-Loop] %s (Runde %d/%d)" % (reason, iteration, MAX_ITER)},
                  sys.stdout)
        return 0
    if action == "halt":
        sys.stderr.write("[Ralph-Loop] HALT: %s\n" % reason)  # eskaliert an den Menschen
    return 0  # STOP/HALT -> Stoppen erlauben


if __name__ == "__main__":
    sys.exit(main())
