#!/usr/bin/env python3
"""WERKBANK Verdikt — uebersetzt Gate-Ergebnisse + Pflichtenheft in ein HARTES Gruen.

Kernregel (gegen "falsches Gruen"):
    GRUEN  <=>  jedes Pflicht-Gate des aktiven Profils hat Status PASS.

Ein Pflicht-Gate ist NICHT gruen, wenn es
  - FAIL ist                         -> VERLETZT
  - SKIP/WARN/gar nicht gelaufen ist -> UNGEDECKT  (egal warum: Tool fehlt, kein Check,
                                                     kein Kontext — "nicht geprueft" zaehlt nie als bestanden)
Zusaetzlich blockt jedes block-Gate, das aktiv FAILt, auch ausserhalb der Pflichtmenge.

Kein externer Dependency (stdlib only); eigener Mini-YAML-Parser fuer pflichtenheft.yaml.
"""
import os
import re

GRUEN = "GRUEN"
ROT = "ROT"


# ---------- Pflichtenheft laden ----------

def _unquote(v):
    v = v.strip()
    m = re.match(r'^"([^"]*)"', v) or re.match(r"^'([^']*)'", v)
    return m.group(1) if m else re.split(r"\s+#", v, maxsplit=1)[0].strip()


def _parse_list(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [x.strip() for x in v.split(",") if x.strip()]


def load_pflichtenheft(path):
    """Liest pflichtenheft.yaml -> {default_profile, profiles: {name: {desc, extends, required}}}."""
    default_profile, profiles, cur, in_profiles = None, {}, None, False
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            stripped = line.strip()
            if indent == 0:
                key = stripped.split(":", 1)[0]
                if key == "default_profile":
                    default_profile = _unquote(stripped.split(":", 1)[1])
                in_profiles = (key == "profiles")
                cur = None
                continue
            if not in_profiles:
                continue
            if indent == 2 and stripped.endswith(":"):
                cur = {"desc": "", "extends": None, "required": []}
                profiles[stripped[:-1].strip()] = cur
                continue
            if cur is None:
                continue
            m = re.match(r"([A-Za-z_]+):\s*(.*)$", stripped)
            if not m:
                continue
            k, v = m.group(1), m.group(2)
            if k == "desc":
                cur["desc"] = _unquote(v)
            elif k == "extends":
                cur["extends"] = _unquote(v) or None
            elif k == "required":
                cur["required"] = _parse_list(v)
    return {"default_profile": default_profile, "profiles": profiles}


def resolve_required(profiles, name):
    """Pflichtmenge eines Profils inkl. aller via `extends` geerbten Gates (Reihenfolge stabil)."""
    if name not in profiles:
        raise KeyError("Profil '%s' nicht im Pflichtenheft (verfuegbar: %s)"
                       % (name, ", ".join(sorted(profiles))))
    req, seen = [], set()

    def walk(n):
        if n in seen:
            return
        seen.add(n)
        p = profiles.get(n)
        if p is None:
            raise KeyError("extends verweist auf unbekanntes Profil '%s'" % n)
        ext = p.get("extends")
        if ext:
            for parent in re.split(r"[,\s]+", ext.strip()):
                if parent:
                    walk(parent)
        for g in p["required"]:
            if g not in req:
                req.append(g)

    walk(name)
    return req


# ---------- Verdikt berechnen ----------

def compute_verdict(required, results, block_fail_gates=()):
    """required: Liste der Pflicht-Gate-IDs.
    results:    dict gid -> {"status": str, "skip_reason": str|None, "summary": str} (gid darf fehlen).
    block_fail_gates: gids von block-Gates, die aktiv FAILen (auch ausserhalb der Pflicht).

    Liefert ein Verdikt-Dict mit GRUEN nur, wenn nichts verletzt UND nichts ungedeckt ist.
    """
    passed, violated, uncovered = [], [], []
    for gid in required:
        r = results.get(gid)
        status = r.get("status") if r else None
        if status == "PASS":
            passed.append(gid)
        elif status == "FAIL":
            violated.append({"gate": gid, "summary": (r or {}).get("summary", "")})
        else:
            if r is None:
                reason, summary = "nicht gelaufen", ""
            else:
                reason = r.get("skip_reason") or (status.lower() if status else "nicht gelaufen")
                summary = r.get("summary", "")
            uncovered.append({"gate": gid, "reason": reason, "summary": summary})

    # Block-Gates, die FAILen, aber NICHT zur Pflichtmenge des Profils gehoeren: rein
    # beratend (im Report sichtbar), aber NICHT verdikt-relevant. Das Profil ist der
    # Vertrag — wer ruff/mypy hart will, nimmt sie ins Profil (z. B. basis). So koennen
    # Fremd-Befunde ein bewusst schmales Profil nicht aushebeln.
    req_set = set(required)
    extra_block_fails = [{"gate": g, "summary": results.get(g, {}).get("summary", "")}
                         for g in block_fail_gates if g not in req_set]

    verdict = GRUEN if not (violated or uncovered) else ROT
    return {
        "verdict": verdict,
        "required": list(required),
        "passed": passed,
        "violated": violated,
        "uncovered": uncovered,
        "extra_block_fails": extra_block_fails,
    }


def select_profile(pflicht, explicit=None):
    """Profilname bestimmen: explizit > default_profile > 'basis'."""
    if explicit:
        return explicit
    return pflicht.get("default_profile") or "basis"


DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pflichtenheft.yaml")
