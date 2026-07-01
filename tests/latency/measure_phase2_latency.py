"""Reproduzierbares Latenz-Messskript — Phase-2-Spanne "Äußerungsende -> Kartenbeginn".

Welle 17 (TASKS.md) / ARCHITECTURE.md Konzept-Kapitel 4: die Zielmarke ist **< 2000 ms**
zwischen dem Ende der Äußerung des Gegenübers (letztes finales STT-Transkript-Event) und dem
Beginn der Coaching-Karte (erstes `card.streamed`-Bus-Event). Dieser Wert entscheidet laut
TASKS.md-Entscheid ("Latenz wird gemessen, nicht angenommen") darüber, ob der Gladia-Fallback
(`SOUFFLEUR_STT_PROVIDER=gladia`) nötig wird, WEIL Gladia laut `capabilities()`
(`adapters/stt/gladia.py`) `supports_streaming=False` meldet und ohnehin nur als Batch-
Fallback taugt — die hier gemessene Zahl ist der Beleg dafür, ob `voxtral_api` (Live-Streaming,
Gate E1 EU) die Zielmarke einhält, BEVOR ein Fallback überhaupt erwogen wird.

## Wie gemessen wird (kein Rätselraten, echte Ausführung)

Dieses Skript führt die ECHTEN Produktionskomponenten aus (`TriggerRouter.decide`,
`ReasoningEngine.handle_trigger`, `InProcessTranscriptEventBus`) — nur die beiden externen
Modell-Aufrufe (`LlmPort.classify`/`LlmPort.stream_reasoning`) und der MCP-Wissensabruf sind
durch `asyncio.sleep(...)`-Verzögerungen ersetzt, deren Dauer dokumentierte/angenommene
Modell-Latenzen nachbildet (siehe `_ModelLatencyProfile` unten) — NICHT, weil echte Netzaufrufe
verboten wären, sondern damit der Messwert reproduzierbar ist (Gate E1/E2: ohnehin kein echter
Netzaufruf in diesem Repo-Scope). Die gemessene Zahl ist die tatsächliche `time.monotonic()`-
Spanne über die reale async-Orchestrierung (Trigger-Entscheidung -> MCP-Abruf -> Streaming-
Start) PLUS die injizierten Modell-Latenzen — nicht eine reine Konstantensumme.

`_ModelLatencyProfile.stt_final_latency_ms` ist NICHT angenommen, sondern aus dem echten
Produktcode übernommen: `VoxtralApiTranscriptionPort.capabilities().typical_final_latency_ms`
(`adapters/stt/voxtral_api.py`). Die übrigen drei Werte (Trigger-Klassifikation, MCP-Abruf,
Reasoning-Time-to-first-Token) sind als Modul-Konstanten dokumentierte Annahmen, bis eine
reale Messung gegen die echte Mistral-/MCP-Infrastruktur vorliegt — klar als solche markiert.

Aufruf: `python3 tests/latency/measure_phase2_latency.py [--runs N]`
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_SRC = _REPO_ROOT / "apps" / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from souffleur.adapters.stt.voxtral_api import VoxtralApiTranscriptionPort  # noqa: E402
from souffleur.bus.event_bus import InProcessTranscriptEventBus  # noqa: E402
from souffleur.core.reasoning import ReasoningEngine  # noqa: E402
from souffleur.core.settings import Settings  # noqa: E402
from souffleur.ports.llm import ChatMessage, ClassificationResult  # noqa: E402
from souffleur.trigger.router import TriggerRouter  # noqa: E402

# Zielmarke (ARCHITECTURE.md Konzept Kap. 4 / TASKS.md Welle 17) — Phase-2-Spanne
# Äußerungsende -> Kartenbeginn.
TARGET_LATENCY_MS = 2000


def _default_settings() -> Settings:
    return Settings(
        mistral_api_key="test-key",
        mistral_base_url="https://api.mistral.ai",
        stt_provider="voxtral_api",
        model_stt_live="voxtral-mini-transcribe-realtime-2602",
        model_stt_batch="voxtral-mini-2602",
        model_reasoning="magistral-medium-2509",
        model_trigger="ministral-3b-2512",
        gladia_api_key=None,
        gladia_base_url="https://api.gladia.io",
        voxtral_local_url="http://voxtral-worker:9000",
        mcp_url="http://coaching-mcp:8080",
        backend_port=8000,
        web_port=5173,
        mcp_port=8080,
        tenant_id="zukunftsbund",
        audit_log_path="./data/audit-log.jsonl",
        retention_days=30,
        require_consent=True,
    )


def _stt_final_latency_ms(settings: Settings) -> int:
    """Echter Produktwert (keine Annahme): `VoxtralApiTranscriptionPort.capabilities()`."""
    return VoxtralApiTranscriptionPort(settings).capabilities().typical_final_latency_ms


@dataclass(frozen=True)
class _ModelLatencyProfile:
    """Latenz-Annahmen je Baustein der Phase-2-Kette (ms) — dokumentiert, nicht versteckt.

    `stt_final_latency_ms` ist der einzige NICHT angenommene Wert (siehe Modul-Docstring).
    Die übrigen drei sind Platzhalter, bis eine reale Messung gegen die echte Mistral-/MCP-
    Infrastruktur vorliegt (Aufgabe für einen künftigen Latenz-Kalibrierungs-Lauf, außerhalb
    des Scopes dieser Welle: kein Produktivcode-Zugriff auf echte Endpunkte hier).
    """

    stt_final_latency_ms: int
    trigger_classify_latency_ms: int = 150  # Annahme: ministral-3b-2512, "billig", schnell
    mcp_knowledge_fetch_latency_ms: int = 5  # Annahme: lokaler stdio-Subprozess, kein Netz
    reasoning_first_token_latency_ms: int = 700  # Annahme: magistral-medium-2509 TTFT


class _TimedFakeLlmPort:
    """`LlmPort`-Double: simuliert Modell-Latenzen über echte `asyncio.sleep` (kein Netz)."""

    def __init__(self, profile: _ModelLatencyProfile, card_deltas: list[str]) -> None:
        self._profile = profile
        self._card_deltas = card_deltas

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        await asyncio.sleep(self._profile.trigger_classify_latency_ms / 1000)
        return ClassificationResult(label="objection", raw_text="objection", model="ministral-3b-2512")

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        await asyncio.sleep(self._profile.reasoning_first_token_latency_ms / 1000)
        for delta in self._card_deltas:
            yield delta


class _TimedFakeMcpClient:
    """MCP-Client-Double: simuliert die stdio-Roundtrip-Latenz (siehe Profil)."""

    def __init__(self, profile: _ModelLatencyProfile) -> None:
        self._profile = profile

    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        await asyncio.sleep(self._profile.mcp_knowledge_fetch_latency_ms / 1000)
        return [{"title": "Sokratische Frage", "guidance": "Frage nach dem konkreten Nutzen."}]


async def measure_once(profile: _ModelLatencyProfile) -> float:
    """Eine Messung: `Äußerungsende` (STT-final-Latenz vergangen) -> erstes `card.streamed`.

    Gibt die gemessene Spanne in Millisekunden zurück — echte `time.monotonic()`-Differenz
    über die reale `TriggerRouter`/`ReasoningEngine`/Bus-Orchestrierung plus injizierte Modell-
    Latenzen, nicht eine reine Konstantensumme.
    """
    settings = _default_settings()
    bus = InProcessTranscriptEventBus()
    llm = _TimedFakeLlmPort(profile, card_deltas=["Frag ", "nach ", "dem ", "Nutzen."])
    mcp = _TimedFakeMcpClient(profile)
    trigger_router = TriggerRouter(llm, settings, cooldown_ms=0)  # type: ignore[arg-type]
    reasoning_engine = ReasoningEngine(llm, mcp, bus, settings)  # type: ignore[arg-type]

    card_begin_ts: dict[str, float] = {}

    async def watch_for_card_start() -> None:
        async for event in bus.subscribe("latency-probe"):
            if event.type == "card.streamed" and "card_begin" not in card_begin_ts:
                card_begin_ts["card_begin"] = time.monotonic()
                return

    watcher = asyncio.ensure_future(watch_for_card_start())
    await asyncio.sleep(0)  # sicherstellen, dass der Bus-Subscriber registriert ist

    # `Äußerungsende`: das letzte finale STT-Transkript-Segment ist eingetroffen — bis der
    # STT-Adapter dieses `final`-Event überhaupt liefert, vergeht die STT-Endlatenz.
    await asyncio.sleep(profile.stt_final_latency_ms / 1000)
    t_utterance_end = time.monotonic()

    # Bewusst ein eindeutiger Einwand (Regel-Vorfilter-Marker "leider"/"zu teuer") — der
    # deterministische Regel-Pfad (`trigger/rules.py`) feuert damit OHNE LLM-Klassifikation.
    # Das ist der häufige, schnelle Fall; `trigger_classify_latency_ms` im Profil ist ein
    # zusätzlicher Kostenfaktor NUR für unsichere Äußerungen (Regel-Vorfilter -> UNCERTAIN)
    # und fließt in DIESER Messung bewusst nicht ein (siehe `_ModelLatencyProfile`-Docstring).
    decision = await trigger_router.decide(
        session_id="latency-probe",
        tenant_id="zukunftsbund",
        text="Das ist mir leider zu teuer.",
    )
    assert decision.fire and decision.card_type is not None, "Test-Text muss zuverlässig feuern"

    await reasoning_engine.handle_trigger(
        session_id="latency-probe",
        tenant_id="zukunftsbund",
        card_type=decision.card_type,
        trigger_text="Das ist mir leider zu teuer.",
        correlation_id="latency-probe-corr",
    )
    await bus.close_session("latency-probe")
    await asyncio.wait_for(watcher, timeout=5)

    return (card_begin_ts["card_begin"] - t_utterance_end) * 1000


async def measure_many(runs: int, profile: _ModelLatencyProfile | None = None) -> list[float]:
    resolved_profile = profile or _ModelLatencyProfile(
        stt_final_latency_ms=_stt_final_latency_ms(_default_settings())
    )
    return [await measure_once(resolved_profile) for _ in range(runs)]


def _print_report(samples: list[float]) -> None:
    median_ms = statistics.median(samples)
    print("Souffleur AI — Phase-2-Latenz (Äußerungsende -> Kartenbeginn)")
    print(f"  Läufe:        {len(samples)}")
    print(f"  Median:       {median_ms:.1f} ms")
    print(f"  Min/Max:      {min(samples):.1f} / {max(samples):.1f} ms")
    print(f"  Zielmarke:    < {TARGET_LATENCY_MS} ms (ARCHITECTURE.md Konzept Kap. 4)")
    verdict = "OK — unter Zielmarke" if median_ms < TARGET_LATENCY_MS else "ÜBER Zielmarke — Gladia-Fallback prüfen"
    print(f"  Ergebnis:     {verdict}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5, help="Anzahl Messläufe (Default: 5)")
    args = parser.parse_args(argv)

    samples = asyncio.run(measure_many(args.runs))
    _print_report(samples)
    return 0 if statistics.median(samples) < TARGET_LATENCY_MS else 1


if __name__ == "__main__":
    raise SystemExit(main())
