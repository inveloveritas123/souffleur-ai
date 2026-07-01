"""Unit-Tests trigger/router.py — Regel-Vorfilter -> LLM-Klassifikator -> Cooldown."""
from __future__ import annotations

import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import FakeLlmPort, SpyAuditLog, default_settings  # noqa: E402
from souffleur.trigger.router import DEFAULT_COOLDOWN_MS, TriggerRouter  # noqa: E402


def _clock_sequence(*values: int):
    it = iter(values)
    return lambda: next(it)


class TriggerRouterRulesPathTest(unittest.IsolatedAsyncioTestCase):
    async def test_neutral_short_text_does_not_fire(self) -> None:
        llm = FakeLlmPort()
        router = TriggerRouter(llm, default_settings(), clock=lambda: 0)

        decision = await router.decide(session_id="s1", tenant_id="t1", text="mhm")

        self.assertFalse(decision.fire)
        self.assertEqual(decision.source, "rules")
        self.assertEqual(llm.classify_calls, [])  # Regel-Vorfilter entscheidet, kein LLM-Aufruf

    async def test_question_fires_via_rules_without_llm_call(self) -> None:
        llm = FakeLlmPort()
        router = TriggerRouter(llm, default_settings(), clock=lambda: 0)

        decision = await router.decide(session_id="s1", tenant_id="t1", text="Was meinen Sie?")

        self.assertTrue(decision.fire)
        self.assertEqual(decision.card_type, "deepening_question")
        self.assertEqual(decision.source, "rules")
        self.assertEqual(llm.classify_calls, [])


class TriggerRouterCooldownTest(unittest.IsolatedAsyncioTestCase):
    async def test_second_trigger_within_cooldown_is_suppressed(self) -> None:
        llm = FakeLlmPort()
        clock = _clock_sequence(0, 1000)  # zweiter Aufruf 1s später, Cooldown 8s
        router = TriggerRouter(llm, default_settings(), clock=clock, cooldown_ms=DEFAULT_COOLDOWN_MS)

        first = await router.decide(session_id="s1", tenant_id="t1", text="Was meinen Sie?")
        second = await router.decide(session_id="s1", tenant_id="t1", text="Und was noch?")

        self.assertTrue(first.fire)
        self.assertFalse(second.fire)
        self.assertIsNone(second.card_type)

    async def test_trigger_after_cooldown_window_fires_again(self) -> None:
        llm = FakeLlmPort()
        clock = _clock_sequence(0, 9000)  # zweiter Aufruf 9s später, > 8s Cooldown
        router = TriggerRouter(llm, default_settings(), clock=clock, cooldown_ms=DEFAULT_COOLDOWN_MS)

        first = await router.decide(session_id="s1", tenant_id="t1", text="Was meinen Sie?")
        second = await router.decide(session_id="s1", tenant_id="t1", text="Und was noch?")

        self.assertTrue(first.fire)
        self.assertTrue(second.fire)

    async def test_cooldown_is_tracked_independently_per_session(self) -> None:
        llm = FakeLlmPort()
        clock = _clock_sequence(0, 100)
        router = TriggerRouter(llm, default_settings(), clock=clock, cooldown_ms=DEFAULT_COOLDOWN_MS)

        first = await router.decide(session_id="s1", tenant_id="t1", text="Was meinen Sie?")
        second = await router.decide(session_id="s2", tenant_id="t1", text="Was denn nun?")

        self.assertTrue(first.fire)
        self.assertTrue(second.fire)  # andere Session, eigener Cooldown-Zähler


class TriggerRouterLlmPathTest(unittest.IsolatedAsyncioTestCase):
    async def test_uncertain_text_is_classified_by_llm_and_fires_for_recognized_label(self) -> None:
        llm = FakeLlmPort(classification_label="objection")
        audit = SpyAuditLog()
        settings = default_settings()
        router = TriggerRouter(llm, settings, audit_log=audit, clock=lambda: 0)  # type: ignore[arg-type]

        decision = await router.decide(
            session_id="s1",
            tenant_id="t1",
            text="Wir haben heute über das Projekt gesprochen",
            correlation_id="corr-1",
        )

        self.assertTrue(decision.fire)
        self.assertEqual(decision.card_type, "objection")
        self.assertEqual(decision.source, "llm")
        self.assertEqual(len(llm.classify_calls), 1)
        self.assertEqual(len(audit.entries), 1)
        self.assertEqual(audit.entries[0].model, settings.model_trigger)
        self.assertEqual(audit.entries[0].correlation_id, "corr-1")

    async def test_uncertain_text_with_no_card_label_does_not_fire(self) -> None:
        llm = FakeLlmPort(classification_label="no_card")
        router = TriggerRouter(llm, default_settings(), clock=lambda: 0)

        decision = await router.decide(
            session_id="s1", tenant_id="t1", text="Wir haben heute über das Projekt gesprochen"
        )

        self.assertFalse(decision.fire)
        self.assertEqual(decision.source, "llm")

    async def test_uncertain_text_with_unrecognized_label_does_not_fire(self) -> None:
        llm = FakeLlmPort(classification_label="ich bin mir nicht sicher")
        router = TriggerRouter(llm, default_settings(), clock=lambda: 0)

        decision = await router.decide(
            session_id="s1", tenant_id="t1", text="Wir haben heute über das Projekt gesprochen"
        )

        self.assertFalse(decision.fire)
        self.assertIsNone(decision.card_type)

    async def test_llm_classify_without_audit_log_does_not_raise(self) -> None:
        llm = FakeLlmPort(classification_label="structure_hint")
        router = TriggerRouter(llm, default_settings(), clock=lambda: 0)  # audit_log=None

        decision = await router.decide(
            session_id="s1", tenant_id="t1", text="Wir haben heute über das Projekt gesprochen"
        )
        self.assertTrue(decision.fire)
        self.assertEqual(decision.card_type, "structure_hint")


if __name__ == "__main__":
    unittest.main()
