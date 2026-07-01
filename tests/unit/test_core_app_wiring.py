"""Unit-Tests core/app.py — Default-Wiring-Zweige von `create_app` (kein echter Netzaufruf).

`create_app(...)` baut bei fehlendem Override die ECHTEN Adapter (`VoxtralApiTranscriptionPort`,
`MistralLlmAdapter`, `GladiaTranscriptionPort`, `CoachingMcpStdioClient`, `TriggerRouter`,
`ReasoningEngine`) — aber jede dieser Konstruktionen ist reine Objekt-Instanziierung ohne
Netz-/Subprozess-Aufruf (verifiziert: `Mistral(...)` telefoniert beim Konstruieren nicht nach
Hause; `CoachingMcpStdioClient` startet den Subprozess laut eigenem Docstring lazy). Diese Tests
decken genau diese Default-Verdrahtungs-Zweige ab, die die E2E-Tests (`tests/e2e/`) mit
injizierten Fakes bewusst umgehen.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import default_settings  # noqa: E402
from souffleur.adapters.llm.mistral import MistralLlmAdapter  # noqa: E402
from souffleur.adapters.mcp.coaching_mcp_client import CoachingMcpStdioClient  # noqa: E402
from souffleur.adapters.stt.gladia import GladiaTranscriptionPort  # noqa: E402
from souffleur.adapters.stt.voxtral_api import VoxtralApiTranscriptionPort  # noqa: E402
from souffleur.audit.audit_log import AuditLog  # noqa: E402
from souffleur.bus.event_bus import InProcessTranscriptEventBus  # noqa: E402
from souffleur.core.app import create_app  # noqa: E402
from souffleur.core.consent import ConsentGate  # noqa: E402
from souffleur.core.reasoning import ReasoningEngine  # noqa: E402
from souffleur.trigger.router import TriggerRouter  # noqa: E402


class CreateAppDefaultWiringTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.mkdtemp(prefix="souffleur-app-wiring-")
        self.addCleanup(shutil.rmtree, self._tmp_dir, ignore_errors=True)
        self._audit_path = os.path.join(self._tmp_dir, "audit.jsonl")

    def test_default_wiring_builds_real_voxtral_adapters_for_default_provider(self) -> None:
        settings = default_settings(audit_log_path=self._audit_path, stt_provider="voxtral_api")

        app = create_app(settings=settings)

        deps = app.state.protocol_deps
        live_deps = app.state.live_deps
        self.assertIs(app.state.deps, deps)  # rückwärtskompatibler Alias
        self.assertIsInstance(deps.transcription_port, VoxtralApiTranscriptionPort)
        self.assertIsInstance(deps.llm_port, MistralLlmAdapter)
        self.assertIsInstance(deps.consent_gate, ConsentGate)
        self.assertIsInstance(deps.audit_log, AuditLog)
        self.assertIsInstance(live_deps.event_bus, InProcessTranscriptEventBus)
        self.assertIsInstance(live_deps.transcription_port, VoxtralApiTranscriptionPort)
        self.assertIsInstance(live_deps.trigger_router, TriggerRouter)
        self.assertIsInstance(live_deps.reasoning_engine, ReasoningEngine)

    def test_default_wiring_for_gladia_provider_uses_factory_for_live_port_too(self) -> None:
        settings = default_settings(audit_log_path=self._audit_path, stt_provider="gladia")

        app = create_app(settings=settings)

        deps = app.state.protocol_deps
        live_deps = app.state.live_deps
        self.assertIsInstance(deps.transcription_port, GladiaTranscriptionPort)
        # Kein `event_bus`-Parameter für Gladia -> Fallback auf dieselbe Factory-Instanz-Art.
        self.assertIsInstance(live_deps.transcription_port, GladiaTranscriptionPort)

    def test_default_mcp_client_is_constructed_lazily_without_spawning_a_process(self) -> None:
        settings = default_settings(audit_log_path=self._audit_path)

        app = create_app(settings=settings)

        mcp_client = app.state.live_deps.reasoning_engine._mcp_client  # type: ignore[attr-defined]
        self.assertIsInstance(mcp_client, CoachingMcpStdioClient)
        self.assertIsNone(mcp_client._process)  # lazy: kein Subprozess bei App-Konstruktion

    def test_routes_include_both_phase1_rest_and_phase2_websocket(self) -> None:
        settings = default_settings(audit_log_path=self._audit_path)
        app = create_app(settings=settings)

        paths = {getattr(route, "path", None) for route in app.routes}
        self.assertIn("/api/v1/consent", paths)
        self.assertIn("/api/v1/protocol", paths)
        self.assertIn("/ws/v1/live", paths)


if __name__ == "__main__":
    unittest.main()
