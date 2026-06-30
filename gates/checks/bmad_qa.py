"""LLM-Urteils-Gates als BMAD-QA-Evidence-Leser — A4, H6, I1, I2, I3.

WERKBANK baut die Urteils-KI NICHT nach (das ist BMADs QA-Agent). Stattdessen liest dieses
Modul den NACHWEIS, den BMADs QA-Agent hinterlegt, und macht daraus ein hartes, auditierbares
Gate. So bleibt das Gate deterministisch + testbar, das Urteil kommt von BMAD, und der Audit-
Trail ist die Evidence-Datei.

Konvention (von der Pipeline-Phase 'QA' geschrieben, nachdem BMADs QA-Agent lief):
    <target>/.werkbank/qa-evidence.json
    {
      "source": "bmad-qa",
      "model": "claude-...",              # Reviewer-/Urteilsmodell
      "implementer_model": "claude-...",  # optional: Modell, das gebaut hat (fuer Cross-Model)
      "reviewed_at": "2026-06-11T...",
      "gates": {
        "A4": {"verdict": "pass|fail", "summary": "...", "reviewer_model": "..."},
        "H6": {...}, "I1": {...}, "I2": {...}, "I3": {...}
      }
    }

Ohne Evidence -> SKIP/NOT_APPLICABLE (unter einem Profil, das das Gate fordert => UNGEDECKT => ROT;
also kein stilles Gruen ohne Nachweis). Verdikt 'fail' -> FAIL. 'pass' -> PASS.
Fuer I1/I2 (Vier-Augen/Tribunal) wird zusaetzlich Cross-Model geprueft, wenn die Modellfelder
vorhanden sind: Reviewer == Implementer => FAIL (kein echtes Vier-Augen-Prinzip).
"""
import json
import os

try:
    from . import common
except ImportError:
    import common  # type: ignore

EVIDENCE_REL = os.path.join(".werkbank", "qa-evidence.json")
_PASS_WORDS = {"pass", "gruen", "grün", "green", "ok", "bestanden"}
_FAIL_WORDS = {"fail", "rot", "red", "durchgefallen", "failed"}
# Gates, die ein anderes Reviewer- als Implementer-Modell verlangen (Vier-Augen/Tribunal).
_CROSS_MODEL = {"I1", "I2"}


def _load_evidence(target):
    p = os.path.join(target, EVIDENCE_REL)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _check(target, gate):
    ev = _load_evidence(target)
    if ev is None:
        return common.skipped(gate, "kein BMAD-QA-Nachweis (.werkbank/qa-evidence.json)",
                              common.NOT_APPLICABLE)
    entry = (ev.get("gates") or {}).get(gate)
    if not isinstance(entry, dict):
        return common.skipped(gate, "BMAD-QA-Nachweis ohne Eintrag fuer %s" % gate,
                              common.NOT_APPLICABLE)
    verdict = str(entry.get("verdict", "")).strip().lower()
    summary = str(entry.get("summary", "")).strip()[:120]
    model = entry.get("reviewer_model") or ev.get("model") or "?"

    if verdict in _FAIL_WORDS:
        return common.CheckResult(gate, common.FAIL,
                                  "BMAD-QA (%s): %s" % (model, summary or "durchgefallen"))
    if verdict not in _PASS_WORDS:
        return common.skipped(gate, "BMAD-QA-Verdikt unklar fuer %s ('%s')" % (gate, verdict),
                              common.NOT_APPLICABLE)

    # Verdikt PASS — fuer Vier-Augen/Tribunal zusaetzlich Cross-Model erzwingen, wenn bekannt.
    if gate in _CROSS_MODEL:
        reviewer = entry.get("reviewer_model") or ev.get("model")
        implementer = ev.get("implementer_model")
        if reviewer and implementer and reviewer == implementer:
            return common.CheckResult(gate, common.FAIL,
                                      "Reviewer == Implementer (%s) — kein Vier-Augen-Prinzip" % reviewer)

    return common.CheckResult(gate, common.PASS, "BMAD-QA (%s): %s" % (model, summary or "bestanden"))


def run_a4(target, **_):
    return _check(target, "A4")


def run_h6(target, **_):
    return _check(target, "H6")


def run_i1(target, **_):
    return _check(target, "I1")


def run_i2(target, **_):
    return _check(target, "I2")


def run_i3(target, **_):
    return _check(target, "I3")
