"""Unit-Tests trigger/rules.py — deterministischer Regel-Vorfilter (kein Modellaufruf)."""
from __future__ import annotations

import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.trigger.rules import (  # noqa: E402
    CARD_TYPE_DEEPENING_QUESTION,
    CARD_TYPE_OBJECTION,
    CARD_TYPE_STRUCTURE_HINT,
    DEFAULT_SILENCE_THRESHOLD_MS,
    RuleDecision,
    apply_rules,
)


class NoCardTest(unittest.TestCase):
    def test_empty_text_is_no_card(self) -> None:
        self.assertEqual(apply_rules("").decision, RuleDecision.NO_CARD)

    def test_whitespace_only_is_no_card(self) -> None:
        self.assertEqual(apply_rules("   ").decision, RuleDecision.NO_CARD)

    def test_too_short_text_is_no_card(self) -> None:
        self.assertEqual(apply_rules("ja gut").decision, RuleDecision.NO_CARD)

    def test_backchannel_phrases_are_no_card(self) -> None:
        for phrase in ("mhm", "ja genau", "okay", "aha", "genau"):
            self.assertEqual(apply_rules(phrase).decision, RuleDecision.NO_CARD, msg=phrase)

    def test_backchannel_with_punctuation_is_still_no_card(self) -> None:
        self.assertEqual(apply_rules("ja?").decision, RuleDecision.NO_CARD)


class QuestionCardTest(unittest.TestCase):
    def test_question_mark_triggers_deepening_question(self) -> None:
        verdict = apply_rules("Was genau meinen Sie damit?")
        self.assertEqual(verdict.decision, RuleDecision.CARD)
        self.assertEqual(verdict.card_type, CARD_TYPE_DEEPENING_QUESTION)

    def test_question_mark_takes_priority_over_objection_marker(self) -> None:
        verdict = apply_rules("Aber ist das nicht zu teuer?")
        self.assertEqual(verdict.card_type, CARD_TYPE_DEEPENING_QUESTION)


class ObjectionCardTest(unittest.TestCase):
    def test_objection_markers_trigger_objection_card(self) -> None:
        for text in (
            "Das ist mir aber zu teuer.",
            "Ich habe da noch Bedenken.",
            "Das funktioniert nicht für uns.",
            "Ehrlich gesagt habe ich Zweifel daran.",
        ):
            verdict = apply_rules(text)
            self.assertEqual(verdict.decision, RuleDecision.CARD, msg=text)
            self.assertEqual(verdict.card_type, CARD_TYPE_OBJECTION, msg=text)


class StructureHintCardTest(unittest.TestCase):
    def test_long_silence_without_markers_triggers_structure_hint(self) -> None:
        verdict = apply_rules("Wir könnten das Thema wechseln", silence_ms=3000)
        self.assertEqual(verdict.decision, RuleDecision.CARD)
        self.assertEqual(verdict.card_type, CARD_TYPE_STRUCTURE_HINT)

    def test_silence_exactly_at_threshold_triggers_structure_hint(self) -> None:
        verdict = apply_rules(
            "Wir könnten das Thema wechseln", silence_ms=DEFAULT_SILENCE_THRESHOLD_MS
        )
        self.assertEqual(verdict.decision, RuleDecision.CARD)

    def test_silence_below_threshold_is_uncertain(self) -> None:
        verdict = apply_rules("Wir könnten das Thema wechseln", silence_ms=100)
        self.assertEqual(verdict.decision, RuleDecision.UNCERTAIN)

    def test_custom_silence_threshold_is_respected(self) -> None:
        verdict = apply_rules(
            "Wir könnten das Thema wechseln", silence_ms=500, silence_threshold_ms=400
        )
        self.assertEqual(verdict.decision, RuleDecision.CARD)
        self.assertEqual(verdict.card_type, CARD_TYPE_STRUCTURE_HINT)


class UncertainTest(unittest.TestCase):
    def test_neutral_statement_without_any_marker_is_uncertain(self) -> None:
        verdict = apply_rules("Wir haben heute über das Projekt gesprochen")
        self.assertEqual(verdict.decision, RuleDecision.UNCERTAIN)
        self.assertIsNone(verdict.card_type)


class RuleDecisionEnumTest(unittest.TestCase):
    def test_enum_values_are_stable_strings(self) -> None:
        self.assertEqual(RuleDecision.NO_CARD.value, "no_card")
        self.assertEqual(RuleDecision.CARD.value, "card")
        self.assertEqual(RuleDecision.UNCERTAIN.value, "uncertain")


if __name__ == "__main__":
    unittest.main()
