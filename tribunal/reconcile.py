#!/usr/bin/env python3
"""I2 — QA-Tribunal: anonymisierte Reconciliation (deterministisch).

Nimmt N Urteile (pass/fail/uncertain) OHNE Modell-Identität (anonymisiert, gleiches Gewicht) und
entscheidet **konservativ**: nur eine klare Pass-Mehrheit (strikte Mehrheit UND mehr pass als fail)
gilt als bestanden — sonst block. `uncertain` zählt nicht als pass. Leer -> block.

CLI:  reconcile.py <verdict> [<verdict> ...]   (verdict in pass|fail|uncertain)
      druckt "decision  pass=.. fail=.. uncertain=.. n=..", Exit 0 (pass) / 3 (block).
"""
import sys


def reconcile(verdicts, policy="conservative"):
    n = len(verdicts)
    p = sum(1 for v in verdicts if v.get("verdict") == "pass")
    f = sum(1 for v in verdicts if v.get("verdict") == "fail")
    u = n - p - f
    decision = "pass" if (n > 0 and p * 2 > n and p > f) else "block"
    reason = ("klare Pass-Mehrheit" if decision == "pass"
              else ("keine Urteile" if n == 0 else "keine klare Pass-Mehrheit (konservativ)"))
    return {"decision": decision, "pass": p, "fail": f, "uncertain": u, "n": n, "reason": reason}


def main(argv):
    verdicts = [{"verdict": a.strip().lower()} for a in argv if a.strip()]
    r = reconcile(verdicts)
    print("%s\tpass=%d fail=%d uncertain=%d n=%d (%s)"
          % (r["decision"], r["pass"], r["fail"], r["uncertain"], r["n"], r["reason"]))
    return 0 if r["decision"] == "pass" else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
