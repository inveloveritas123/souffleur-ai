"""Unit-Tests core/reasoning.py — ReasoningEngine: MCP-Wissen -> Streaming-Karte -> Bus/Audit."""
from __future__ import annotations

import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import (  # noqa: E402
    FakeCoachingKnowledgeClient,
    FakeLlmPort,
    SpyAuditLog,
    default_settings,
)
from souffleur.bus.event_bus import BusEvent, InProcessTranscriptEventBus  # noqa: E402
from souffleur.core.reasoning import ReasoningEngine, _build_card_prompt  # noqa: E402


class ReasoningEngineHandleTriggerTest(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_trigger_fired_card_streamed_and_card_proposed_in_order(self) -> None:
        llm = FakeLlmPort(reasoning_deltas=["Frag ", "nach ", "dem ", "Warum."])
        mcp = FakeCoachingKnowledgeClient(
            knowledge=[{"title": "Sokratische Frage", "guidance": "Frage nach dem Warum."}]
        )
        bus = InProcessTranscriptEventBus()
        audit = SpyAuditLog()
        engine = ReasoningEngine(
            llm, mcp, bus, default_settings(), audit_log=audit  # type: ignore[arg-type]
        )

        received: list[BusEvent] = []

        import asyncio

        async def consume() -> None:
            async for event in bus.subscribe("session-1"):
                received.append(event)

        task = asyncio.ensure_future(consume())
        await asyncio.sleep(0)

        card_text = await engine.handle_trigger(
            session_id="session-1",
            tenant_id="zukunftsbund",
            card_type="deepening_question",
            trigger_text="Das ist mir zu teuer.",
            correlation_id="corr-1",
        )
        await bus.close_session("session-1")
        await asyncio.wait_for(task, timeout=1)

        self.assertEqual(card_text, "Frag nach dem Warum.")
        types = [event.type for event in received]
        self.assertEqual(
            types,
            ["trigger.fired", "card.streamed", "card.streamed", "card.streamed", "card.streamed", "card.proposed"],
        )
        self.assertEqual(received[0].payload.text, "deepening_question")
        self.assertEqual(received[-1].payload.text, card_text)
        self.assertEqual(mcp.calls, [("deepening_question", "Das ist mir zu teuer.", 3)])

        self.assertEqual(len(audit.entries), 1)
        self.assertEqual(audit.entries[0].action, "model_call")
        self.assertEqual(audit.entries[0].model, "magistral-medium-2509")
        self.assertEqual(audit.entries[0].correlation_id, "corr-1")
        # Gate E2: das Audit-Log darf niemals den Kartentext tragen.
        self.assertNotIn(card_text, audit.entries[0].to_dict().values())

    async def test_empty_deltas_are_skipped_and_card_text_can_be_empty(self) -> None:
        llm = FakeLlmPort(reasoning_deltas=["", "Text.", ""])
        mcp = FakeCoachingKnowledgeClient(knowledge=[])
        bus = InProcessTranscriptEventBus()
        engine = ReasoningEngine(llm, mcp, bus, default_settings())  # ohne audit_log

        card_text = await engine.handle_trigger(
            session_id="s1",
            tenant_id="t1",
            card_type="objection",
            trigger_text="Das funktioniert nicht.",
            correlation_id="corr-2",
        )

        self.assertEqual(card_text, "Text.")


class BuildCardPromptTest(unittest.TestCase):
    def test_prompt_includes_card_type_and_trigger_text(self) -> None:
        messages = _build_card_prompt(
            "objection", "Das ist zu teuer.", [{"title": "Einwandbehandlung", "summary": "..."}]
        )
        self.assertEqual(messages[0].role, "system")
        self.assertEqual(messages[1].role, "user")
        self.assertIn("objection", messages[1].content)
        self.assertIn("Das ist zu teuer.", messages[1].content)
        self.assertIn("Einwandbehandlung", messages[1].content)

    def test_prompt_without_knowledge_uses_fallback_text(self) -> None:
        messages = _build_card_prompt("structure_hint", "...", [])
        self.assertIn("kein spezifisches Wissen gefunden", messages[1].content)


if __name__ == "__main__":
    unittest.main()
