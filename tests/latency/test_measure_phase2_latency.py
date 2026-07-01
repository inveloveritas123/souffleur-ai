"""Test für das Latenz-Messskript selbst — reproduzierbar (feste Sleep-Profile, kein Netz).

Exekutiert nebenbei echten Produktcode (`TriggerRouter`, `ReasoningEngine`,
`InProcessTranscriptEventBus`, `VoxtralApiTranscriptionPort.capabilities`) — trägt also auch
zur Gate-C2-Coverage bei, ist aber primär der Nachweis, dass das Messskript tatsächlich einen
plausiblen, reproduzierbaren Wert liefert (TASKS.md Welle 17: "Latenz wird gemessen, nicht
angenommen").
"""
from __future__ import annotations

import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from . import measure_phase2_latency as latency_script  # noqa: E402


class MeasureOnceTest(unittest.IsolatedAsyncioTestCase):
    async def test_measured_latency_is_positive_and_at_least_the_injected_delays(self) -> None:
        profile = latency_script._ModelLatencyProfile(
            stt_final_latency_ms=0,  # STT-Endlatenz fließt NICHT in die gemessene Spanne ein
            trigger_classify_latency_ms=0,  # Regel-Vorfilter feuert hier ohnehin (kein LLM-Call)
            mcp_knowledge_fetch_latency_ms=10,
            reasoning_first_token_latency_ms=20,
        )

        elapsed_ms = await latency_script.measure_once(profile)

        # Untere Schranke: MCP-Abruf + Reasoning-TTFT MÜSSEN in der Spanne stecken.
        self.assertGreaterEqual(elapsed_ms, 25.0)
        # Obere Schranke: reine Orchestrierungs-Overhead darf die injizierten Latenzen nicht
        # um Größenordnungen übersteigen (Regressions-Wächter für dieses Skript).
        self.assertLess(elapsed_ms, 500.0)

    async def test_stt_final_latency_ms_is_read_from_real_product_capabilities(self) -> None:
        settings = latency_script._default_settings()
        value = latency_script._stt_final_latency_ms(settings)
        self.assertEqual(value, 300)  # VoxtralApiTranscriptionPort.capabilities() (Welle 4/12)


class MeasureManyAndReportTest(unittest.IsolatedAsyncioTestCase):
    async def test_measure_many_returns_one_sample_per_run(self) -> None:
        profile = latency_script._ModelLatencyProfile(
            stt_final_latency_ms=0,
            trigger_classify_latency_ms=0,
            mcp_knowledge_fetch_latency_ms=1,
            reasoning_first_token_latency_ms=1,
        )
        samples = await latency_script.measure_many(3, profile=profile)
        self.assertEqual(len(samples), 3)
        self.assertTrue(all(sample > 0 for sample in samples))

    def test_print_report_and_target_latency_constant(self) -> None:
        self.assertEqual(latency_script.TARGET_LATENCY_MS, 2000)
        latency_script._print_report([100.0, 150.0, 200.0])  # darf nicht werfen


class MainEntryPointTest(unittest.TestCase):
    def test_main_returns_zero_when_median_is_under_target(self) -> None:
        exit_code = latency_script.main(["--runs", "2"])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
