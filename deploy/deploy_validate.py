#!/usr/bin/env python3
"""I3 — Deployment-Validierung (Argus-Stil), deterministische Aggregation.

Gegen echte User-Flows: **ALLE** kritischen Flows müssen `pass` sein, sonst block (strenger als
das Tribunal). Die Flow-Urteile selbst sind LLM/Test-generiert (nicht deterministisch); diese
Aggregation ist es.

CLI:  deploy_validate.py <verdict> [<verdict> ...]   (pass|fail|uncertain)
      Exit 0 (deploy) / 3 (block).
"""
import sys


def validate(flows):
    n = len(flows)
    passed = sum(1 for f in flows if f.get("verdict") == "pass")
    decision = "deploy" if (n > 0 and passed == n) else "block"
    reason = ("alle %d Flows bestanden" % n if decision == "deploy"
              else ("keine Flows" if n == 0 else "%d/%d Flows bestanden — Deployment blockiert" % (passed, n)))
    return {"decision": decision, "passed": passed, "n": n, "reason": reason}


def main(argv):
    flows = [{"verdict": a.strip().lower()} for a in argv if a.strip()]
    r = validate(flows)
    print("%s\t%s" % (r["decision"], r["reason"]))
    return 0 if r["decision"] == "deploy" else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
