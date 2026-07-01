"""Welle 13 — TriggerRouter, Regel-Vorfilter und ReasoningEngine (+ MCP-Anbindung).

Deterministischer Regelpfad ohne Modellaufruf (SPEC.md Akzeptanz: neutrale Aussage -> keine
Karte, Einwand/Frage -> Karte). `ministral-3b-2512`- und `magistral-medium-2509`-Aufrufe sind
über gefälschte `LlmPort`-Implementierungen ersetzt (keine echten Netzaufrufe, Gate E1/E2).
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from souffleur.audit.audit_log import AuditLog
from souffleur.bus import InProcessTranscriptEventBus
from souffleur.core.reasoning import ReasoningEngine
from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage, ClassificationResult
from souffleur.trigger.router import TriggerRouter
from souffleur.trigger.rules import RuleDecision, apply_rules


def _settings() -> Settings:
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


class FakeLlmPort:
    """Gefälschter LlmPort: kein Netzaufruf, protokolliert alle Aufrufe für Assertions."""

    def __init__(
        self,
        classify_label: str = "no_card",
        stream_chunks: list[str] | None = None,
    ) -> None:
        self.classify_calls: list[list[ChatMessage]] = []
        self.stream_calls: list[list[ChatMessage]] = []
        self._classify_label = classify_label
        self._stream_chunks = stream_chunks if stream_chunks is not None else ["Frage", " nach dem Budget."]

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        self.classify_calls.append(messages)
        return ClassificationResult(
            label=self._classify_label, raw_text=self._classify_label, model="ministral-3b-2512"
        )

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        self.stream_calls.append(messages)
        for chunk in self._stream_chunks:
            yield chunk


class FakeMcpClient:
    """Gefälschter Coaching-MCP-Client (stdio wird in test_mcp_client.py separat getestet)."""

    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[tuple[str, str | None, int]] = []
        self._entries = entries if entries is not None else [
            {"id": "k1", "card_type": "objection", "title": "Reframe", "guidance": "Frage nach dem Warum."}
        ]

    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:
        self.calls.append((card_type, query, limit))
        return self._entries


# --- Regel-Vorfilter (deterministisch, SPEC.md Akzeptanz) -----------------------------


def test_apply_rules_neutral_statement_never_fires_card_directly() -> None:
    """Regel-Vorfilter: eine neutrale Aussage (kein '?', kein Einwand-Marker) ist nie CARD."""
    verdict = apply_rules("Wir haben letzte Woche über die Ziele gesprochen und alles war klar.")

    assert verdict.decision != RuleDecision.CARD


def test_apply_rules_question_returns_card_deepening_question() -> None:
    verdict = apply_rules("Was genau meinen Sie mit 'zu spät'?")

    assert verdict.decision == RuleDecision.CARD
    assert verdict.card_type == "deepening_question"


def test_apply_rules_objection_marker_returns_card_objection() -> None:
    verdict = apply_rules("Das Budget ist mir ehrlich gesagt zu hoch.")

    assert verdict.decision == RuleDecision.CARD
    assert verdict.card_type == "objection"


def test_apply_rules_backchannel_returns_no_card() -> None:
    for backchannel in ("mhm", "ja genau", "okay"):
        assert apply_rules(backchannel).decision == RuleDecision.NO_CARD


def test_apply_rules_too_short_segment_returns_no_card() -> None:
    assert apply_rules("ja?").decision == RuleDecision.NO_CARD


def test_apply_rules_long_silence_returns_structure_hint() -> None:
    verdict = apply_rules("Ich denke gerade nach.", silence_ms=3000, silence_threshold_ms=2500)

    assert verdict.decision == RuleDecision.CARD
    assert verdict.card_type == "structure_hint"


# --- TriggerRouter: Regel-Fast-Path (kein Modellaufruf) -------------------------------


def test_router_fires_card_on_objection_without_calling_llm() -> None:
    llm = FakeLlmPort()
    router = TriggerRouter(llm, _settings())

    decision = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text="Das ist mir zu teuer.")
    )

    assert decision.fire is True
    assert decision.card_type == "objection"
    assert decision.source == "rules"
    assert llm.classify_calls == []  # Regel-Fast-Path: kein ministral-3b-Aufruf


def test_router_returns_no_card_for_neutral_statement_without_calling_llm() -> None:
    llm = FakeLlmPort()
    router = TriggerRouter(llm, _settings())

    decision = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text="mhm")
    )

    assert decision.fire is False
    assert llm.classify_calls == []


# --- TriggerRouter: unsicherer Fall -> ministral-3b-2512 ------------------------------


def _uncertain_text() -> str:
    """Ein Segment, das keine Regel triggert (kein '?', kein Marker, keine lange Stille)."""
    return "Wir haben letzte Woche über die neuen Ziele fürs Team gesprochen und Notizen gemacht."


def test_router_calls_llm_classifier_when_rules_are_uncertain() -> None:
    assert apply_rules(_uncertain_text()).decision == RuleDecision.UNCERTAIN

    llm = FakeLlmPort(classify_label="objection")
    router = TriggerRouter(llm, _settings())

    decision = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text=_uncertain_text())
    )

    assert len(llm.classify_calls) == 1
    assert decision.fire is True
    assert decision.card_type == "objection"
    assert decision.source == "llm"


def test_router_llm_no_card_label_suppresses_card() -> None:
    llm = FakeLlmPort(classify_label="no_card")
    router = TriggerRouter(llm, _settings())

    decision = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text=_uncertain_text())
    )

    assert decision.fire is False
    assert decision.card_type is None


def test_router_records_audit_entry_for_classify_model_call(tmp_path: Any) -> None:
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    llm = FakeLlmPort(classify_label="structure_hint")
    router = TriggerRouter(llm, _settings(), audit_log=audit_log)

    asyncio.run(
        router.decide(
            session_id="s1",
            tenant_id="zukunftsbund",
            text=_uncertain_text(),
            correlation_id="corr-1",
        )
    )

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["action"] == "model_call"
    assert entry["model"] == "ministral-3b-2512"
    assert entry["routing_region"] == "EU"
    assert entry["pii_present"] is False


# --- TriggerRouter: Cooldown gegen Karten-Spam ----------------------------------------


def test_cooldown_suppresses_second_trigger_within_window() -> None:
    clock = {"now": 0}
    router = TriggerRouter(
        FakeLlmPort(), _settings(), cooldown_ms=5000, clock=lambda: clock["now"]
    )

    first = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text="Das ist mir zu teuer.")
    )
    clock["now"] = 1000  # innerhalb des Cooldown-Fensters
    second = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text="Das Angebot passt nicht.")
    )
    clock["now"] = 6001  # außerhalb des Cooldown-Fensters
    third = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text="Das Budget ist zu hoch.")
    )

    assert first.fire is True
    assert second.fire is False  # unterdrückt durch Cooldown
    assert third.fire is True  # Cooldown abgelaufen


def test_cooldown_short_circuits_before_llm_classify_call() -> None:
    """Finding 12 (Trigger-Kosten vor Cooldown): der Cooldown-Check muss VOR dem bezahlten
    `ministral-3b`-classify-Aufruf greifen — vorher wurde bei UNCERTAIN immer zuerst
    klassifiziert und der Cooldown erst danach geprüft, was während des Cooldown-Fensters
    unnötige, bezahlte Modellaufrufe verursachte."""
    clock = {"now": 0}
    llm = FakeLlmPort(classify_label="objection")
    router = TriggerRouter(llm, _settings(), cooldown_ms=5000, clock=lambda: clock["now"])

    # 1) Regel-Treffer setzt den Cooldown.
    first = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text="Das ist mir zu teuer.")
    )
    assert first.fire is True
    assert llm.classify_calls == []

    # 2) Innerhalb des Cooldown-Fensters: ein UNCERTAIN-Segment darf NICHT mehr klassifiziert
    # werden — der Cooldown muss den teuren Modellaufruf verhindern, nicht erst danach greifen.
    clock["now"] = 1000
    second = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text=_uncertain_text())
    )
    assert second.fire is False
    assert llm.classify_calls == []  # kein bezahlter Aufruf während des Cooldowns

    # 3) Nach Ablauf des Cooldowns wird wieder klassifiziert.
    clock["now"] = 6001
    third = asyncio.run(
        router.decide(session_id="s1", tenant_id="zukunftsbund", text=_uncertain_text())
    )
    assert len(llm.classify_calls) == 1
    assert third.fire is True
    assert third.card_type == "objection"


def test_forget_session_removes_cooldown_state_leak() -> None:
    """Finding 15 (Leak): `_last_fired_at_ms` wächst unbegrenzt über die Prozesslaufzeit, wenn
    Einträge nach Session-Ende nie entfernt werden. `forget_session` räumt den Eintrag auf —
    danach verhält sich die Session wie eine brandneue (kein Rest-Cooldown)."""
    clock = {"now": 0}
    router = TriggerRouter(FakeLlmPort(), _settings(), cooldown_ms=5000, clock=lambda: clock["now"])

    asyncio.run(router.decide(session_id="s1", tenant_id="zukunftsbund", text="Das ist mir zu teuer."))
    assert "s1" in router._last_fired_at_ms  # noqa: SLF001 - internen Zustand für den Leak-Test prüfen

    router.forget_session("s1")

    assert "s1" not in router._last_fired_at_ms  # noqa: SLF001
    # forget_session auf einer unbekannten/bereits vergessenen Session darf nicht crashen.
    router.forget_session("does-not-exist")


def test_cooldown_is_independent_per_session() -> None:
    clock = {"now": 0}
    router = TriggerRouter(
        FakeLlmPort(), _settings(), cooldown_ms=5000, clock=lambda: clock["now"]
    )

    decision_a = asyncio.run(
        router.decide(session_id="session-a", tenant_id="zukunftsbund", text="Das ist mir zu teuer.")
    )
    decision_b = asyncio.run(
        router.decide(session_id="session-b", tenant_id="zukunftsbund", text="Das Budget ist zu hoch.")
    )

    assert decision_a.fire is True
    assert decision_b.fire is True  # andere Session, eigener Cooldown


# --- ReasoningEngine: MCP-Wissen -> gestreamte Karte -> Bus ---------------------------


def test_reasoning_engine_publishes_trigger_fired_streamed_and_proposed_in_order() -> None:
    llm = FakeLlmPort(stream_chunks=["Frag", " nach", " dem Warum."])
    mcp = FakeMcpClient()
    bus = InProcessTranscriptEventBus()
    engine = ReasoningEngine(llm, mcp, bus, _settings())

    async def scenario() -> list[Any]:
        received: list[Any] = []

        async def consume() -> None:
            async for event in bus.subscribe("session-1"):
                received.append(event)
                if event.type == "card.proposed":
                    return

        consumer = asyncio.ensure_future(consume())
        await asyncio.sleep(0)

        card_text = await engine.handle_trigger(
            session_id="session-1",
            tenant_id="zukunftsbund",
            card_type="objection",
            trigger_text="Das Budget ist mir zu hoch.",
            correlation_id="corr-1",
        )
        await asyncio.wait_for(consumer, timeout=1)
        return received + [card_text]

    received = asyncio.run(scenario())
    *events, card_text = received

    assert card_text == "Frag nach dem Warum."
    assert [e.type for e in events] == [
        "trigger.fired",
        "card.streamed",
        "card.streamed",
        "card.streamed",
        "card.proposed",
    ]
    assert events[0].payload.text == "objection"
    assert events[-1].payload.text == "Frag nach dem Warum."
    assert [e.seq for e in events] == [1, 2, 3, 4, 5]
    assert all(e.correlation_id == "corr-1" for e in events)


def test_reasoning_engine_fetches_knowledge_from_mcp_with_card_type_and_query() -> None:
    llm = FakeLlmPort(stream_chunks=["Karte."])
    mcp = FakeMcpClient()
    bus = InProcessTranscriptEventBus()
    engine = ReasoningEngine(llm, mcp, bus, _settings())

    asyncio.run(
        engine.handle_trigger(
            session_id="s1",
            tenant_id="zukunftsbund",
            card_type="objection",
            trigger_text="Das Budget ist mir zu hoch.",
            correlation_id="corr-1",
        )
    )

    assert mcp.calls == [("objection", "Das Budget ist mir zu hoch.", 3)]
    # Das MCP-Wissen fließt in den Reasoning-Prompt ein (Karten-Personalisierung).
    prompt_text = " ".join(m.content for m in llm.stream_calls[0])
    assert "Reframe" in prompt_text


def test_reasoning_engine_records_audit_entry_for_reasoning_model_call(tmp_path: Any) -> None:
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    llm = FakeLlmPort(stream_chunks=["Karte."])
    mcp = FakeMcpClient()
    bus = InProcessTranscriptEventBus()
    engine = ReasoningEngine(llm, mcp, bus, _settings(), audit_log=audit_log)

    asyncio.run(
        engine.handle_trigger(
            session_id="s1",
            tenant_id="zukunftsbund",
            card_type="objection",
            trigger_text="Das Budget ist mir zu hoch.",
            correlation_id="corr-1",
        )
    )

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["model"] == "magistral-medium-2509"
    assert entry["action"] == "model_call"
    assert entry["pii_present"] is False
