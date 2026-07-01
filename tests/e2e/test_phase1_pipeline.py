"""E2E — Phase-1-Pipeline (Upload bis Protokoll), Welle 17 Akzeptanz.

Fährt die volle FastAPI-App (`souffleur.core.app.create_app`) über
`fastapi.testclient.TestClient` (Starlette/httpx `ASGITransport` unter der Haube) — echte
Routen, echter `ConsentGate`/`AuditLog`, aber gemockte STT-/LLM-Adapter (kein echtes Mistral,
Gate E1/E2: keine echten Netzaufrufe). Prüft explizit die Consent-Pflicht (403 ohne gültige
Einwilligung) und den vollständigen Erfolgspfad (Consent -> Upload -> diarisiertes Protokoll).
"""
from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from collections.abc import AsyncIterator
from typing import Any

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import default_settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from souffleur.core.app import create_app  # noqa: E402
from souffleur.ports.llm import ChatMessage, ClassificationResult  # noqa: E402
from souffleur.ports.types import (  # noqa: E402
    AudioRef,
    BatchOptions,
    ProviderCapabilities,
    TranscriptEvent,
    TranscriptResult,
    Word,
)


class _FakeBatchTranscriptionPort:
    """Erfüllt nur, was Phase 1 nutzt (`transcribe_batch`/`capabilities`) — Live-Stubs unbenutzt."""

    def __init__(self) -> None:
        self.received_audio: AudioRef | None = None
        self.received_opts: BatchOptions | None = None

    async def open_stream(self, session: Any) -> Any:  # pragma: no cover - Phase 1 nutzt das nicht
        raise NotImplementedError

    async def push_audio(self, handle: Any, pcm_chunk: bytes) -> None:  # pragma: no cover
        raise NotImplementedError

    async def events(self, handle: Any) -> AsyncIterator[TranscriptEvent]:  # pragma: no cover
        raise NotImplementedError
        yield  # macht die Methode zum Async-Generator

    async def close_stream(self, handle: Any) -> TranscriptResult:  # pragma: no cover
        raise NotImplementedError

    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult:
        self.received_audio = audio
        self.received_opts = opts
        return TranscriptResult(
            segments=[
                TranscriptEvent(
                    kind="final",
                    speaker="speaker_0",
                    text="Ich habe da noch Bedenken wegen des Preises.",
                    t_start_ms=0,
                    t_end_ms=2000,
                    words=[Word(text="Bedenken", t_start_ms=500, t_end_ms=900)],
                ),
                TranscriptEvent(
                    kind="final", speaker="speaker_1", text="Lassen Sie uns das klären.",
                    t_start_ms=2000, t_end_ms=4000,
                ),
            ],
            speakers=["speaker_0", "speaker_1"],
            duration_ms=4000,
            model="voxtral-mini-2602",
            provider="voxtral_api",
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=True, supports_diarization=True, supports_word_timestamps=True,
            typical_final_latency_ms=300,
        )


class _FakeSummaryLlmPort:
    """`LlmPort`-Double — `stream_reasoning` liefert eine feste Zusammenfassung; `classify` ungenutzt."""

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        yield "Zusammenfassung: "
        yield "Preis-Einwand geklärt."

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:  # pragma: no cover
        raise NotImplementedError


def _build_test_app(tmp_audit_path: str) -> tuple[TestClient, _FakeBatchTranscriptionPort]:
    settings = default_settings(audit_log_path=tmp_audit_path)
    transcription_port = _FakeBatchTranscriptionPort()
    app = create_app(
        settings=settings,
        transcription_port=transcription_port,
        llm_port=_FakeSummaryLlmPort(),  # type: ignore[arg-type]
        live_transcription_port=transcription_port,  # nicht Phase-1-relevant, aber erforderlich
        mcp_client=_NullMcpClient(),
        trigger_router=None,
        reasoning_engine=None,
    )
    return TestClient(app), transcription_port


class _NullMcpClient:
    """Wird von `create_app` für den (in diesen Tests ungenutzten) Live-Pfad verdrahtet."""

    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]:  # pragma: no cover
        return []


class Phase1PipelineE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.mkdtemp(prefix="souffleur-e2e-")
        self.addCleanup(shutil.rmtree, self._tmp_dir, ignore_errors=True)
        self._audit_path = os.path.join(self._tmp_dir, "audit-log.jsonl")

    def _read_audit_lines(self) -> list[str]:
        if not os.path.exists(self._audit_path):
            return []
        with open(self._audit_path, encoding="utf-8") as handle:
            return [line for line in handle if line.strip()]

    def test_upload_without_consent_ref_is_rejected_with_403(self) -> None:
        client, _port = _build_test_app(self._audit_path)

        response = client.post(
            "/api/v1/protocol",
            data={"consent_ref": "never-granted"},
            files={"audio": ("session.wav", io.BytesIO(b"fake-audio-bytes"), "audio/wav")},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.json())

        audit_lines = self._read_audit_lines()
        self.assertTrue(any('"result": "denied"' in line for line in audit_lines))

    def test_full_pipeline_consent_upload_protocol(self) -> None:
        client, port = _build_test_app(self._audit_path)

        consent_response = client.post(
            "/api/v1/consent",
            json={
                "tenant_id": "zukunftsbund",
                "session_id": "session-e2e",
                "participant_acknowledged": True,
                "text_version": "v1.0",
            },
        )
        self.assertEqual(consent_response.status_code, 200)
        consent_ref = consent_response.json()["consent_ref"]
        self.assertEqual(consent_response.json()["text_version"], "v1.0")

        protocol_response = client.post(
            "/api/v1/protocol",
            data={
                "consent_ref": consent_ref,
                "tenant_id": "zukunftsbund",
                "session_id": "session-e2e",
            },
            files={"audio": ("session.wav", io.BytesIO(b"fake-audio-bytes"), "audio/wav")},
        )
        self.assertEqual(protocol_response.status_code, 200)
        body = protocol_response.json()

        self.assertEqual(body["tenant_id"], "zukunftsbund")
        self.assertEqual(body["session_id"], "session-e2e")
        self.assertEqual(body["duration_ms"], 4000)
        self.assertEqual(body["stt_model"], "voxtral-mini-2602")
        self.assertEqual(body["reasoning_model"], "magistral-medium-2509")
        self.assertEqual(body["speakers"], ["speaker_0", "speaker_1"])
        self.assertEqual(len(body["segments"]), 2)
        self.assertEqual(body["segments"][0]["speaker"], "speaker_0")
        self.assertEqual(body["segments"][0]["words"][0]["text"], "Bedenken")
        self.assertEqual(body["summary"], "Zusammenfassung: Preis-Einwand geklärt.")

        self.assertIsNotNone(port.received_audio)
        assert port.received_opts is not None
        self.assertTrue(port.received_opts.diarization)
        self.assertTrue(port.received_opts.word_timestamps)

        # GET liefert dasselbe Protokoll zurück (Finding 2, BLOCKER IDOR: consent_ref Pflicht).
        get_response = client.get(
            f"/api/v1/protocol/{body['id']}", params={"consent_ref": consent_ref}
        )
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["summary"], body["summary"])

        # Je Modellaufruf genau ein Audit-Eintrag (STT-Batch + Reasoning), plus 1 für Consent-Create.
        audit_lines = self._read_audit_lines()
        self.assertEqual(len(audit_lines), 3)
        self.assertTrue(all('"routing_region": "EU"' in line for line in audit_lines))
        self.assertTrue(all('"pii_present": false' in line for line in audit_lines))
        # Gate E2: der Kartentext/Gesprächsinhalt darf nie im Audit-Log auftauchen.
        for line in audit_lines:
            self.assertNotIn("Bedenken", line)
            self.assertNotIn("Zusammenfassung", line)

    def test_get_unknown_protocol_id_returns_404(self) -> None:
        client, _port = _build_test_app(self._audit_path)
        consent_response = client.post(
            "/api/v1/consent", json={"participant_acknowledged": True, "text_version": "v1.0"}
        )
        consent_ref = consent_response.json()["consent_ref"]

        response = client.get(
            "/api/v1/protocol/does-not-exist", params={"consent_ref": consent_ref}
        )
        self.assertEqual(response.status_code, 404)

    def test_get_protocol_without_consent_ref_is_rejected_with_403(self) -> None:
        """Finding 2 (BLOCKER IDOR): ohne consent_ref darf niemand ein Protokoll lesen —
        selbst nicht das eigene."""
        client, _port = _build_test_app(self._audit_path)
        response = client.get("/api/v1/protocol/does-not-exist")
        self.assertEqual(response.status_code, 403)

    def test_protocol_upload_for_wrong_tenant_consent_is_rejected(self) -> None:
        client, _port = _build_test_app(self._audit_path)

        consent_response = client.post(
            "/api/v1/consent",
            json={
                "tenant_id": "tenant-a",
                "participant_acknowledged": True,
                "text_version": "v1.0",
            },
        )
        consent_ref = consent_response.json()["consent_ref"]

        response = client.post(
            "/api/v1/protocol",
            data={"consent_ref": consent_ref, "tenant_id": "tenant-b"},
            files={"audio": ("session.wav", io.BytesIO(b"x"), "audio/wav")},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
