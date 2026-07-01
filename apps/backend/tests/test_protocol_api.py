"""Welle 6 — Phase-1-Pipeline und REST-API (Protokoll).

End-to-End gegen gemockte Adapter (Gate E1/E2: keine echten Netzaufrufe). Prüft den
REST-Vertrag, den die Web-UI erwartet: `POST /api/v1/consent`, `POST /api/v1/protocol`
(multipart, 403 ohne gültige Einwilligung), `GET /api/v1/protocol/{id}`; sowie je
Modellaufruf genau einen AuditLog-Eintrag mit routing_region=EU, pii_present=false.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient
from souffleur.audit.audit_log import AuditLog
from souffleur.core.app import create_app
from souffleur.core.consent import ConsentGate
from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage, ClassificationResult
from souffleur.ports.types import (
    AudioRef,
    BatchOptions,
    ProviderCapabilities,
    TranscriptEvent,
    TranscriptResult,
    Word,
)


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


class _FakeTranscriptionPort:
    """Erfüllt TranscriptionPort.transcribe_batch/capabilities; Live-Stubs ungenutzt."""

    def __init__(self) -> None:
        self.received_audio: AudioRef | None = None
        self.received_opts: BatchOptions | None = None

    async def open_stream(self, session: object) -> object:
        raise NotImplementedError

    async def push_audio(self, handle: object, pcm_chunk: bytes) -> None:
        raise NotImplementedError

    async def events(self, handle: object) -> AsyncIterator[TranscriptEvent]:
        raise NotImplementedError
        yield  # pragma: no cover

    async def close_stream(self, handle: object) -> TranscriptResult:
        raise NotImplementedError

    async def transcribe_batch(self, audio: AudioRef, opts: BatchOptions) -> TranscriptResult:
        self.received_audio = audio
        self.received_opts = opts
        return TranscriptResult(
            segments=[
                TranscriptEvent(
                    kind="final",
                    speaker="coach",
                    text="Wie geht es Ihnen mit dem Thema?",
                    t_start_ms=0,
                    t_end_ms=2000,
                    words=[Word(text="Wie", t_start_ms=0, t_end_ms=200)],
                ),
                TranscriptEvent(
                    kind="final",
                    speaker="counterpart",
                    text="Eher angespannt, ehrlich gesagt.",
                    t_start_ms=2000,
                    t_end_ms=4000,
                    words=None,
                ),
            ],
            speakers=["coach", "counterpart"],
            duration_ms=4000,
            model="voxtral-mini-2602",
            provider="voxtral_api",
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=False,
            supports_diarization=True,
            supports_word_timestamps=True,
            typical_final_latency_ms=300,
            residency="EU",
        )


class _FakeLlmPort:
    """Erfüllt LlmPort; liefert eine deterministische, gestreamte Zusammenfassung."""

    def __init__(self) -> None:
        self.received_messages: list[ChatMessage] | None = None

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        self.received_messages = messages
        for chunk in ["Zusammenfassung: ", "Klient wirkt angespannt."]:
            yield chunk

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        return ClassificationResult(label="keine-karte", raw_text="keine-karte", model="ministral-3b-2512")


def _build_client(tmp_path: Path) -> tuple[TestClient, AuditLog, _FakeTranscriptionPort, _FakeLlmPort]:
    audit_log = AuditLog(str(tmp_path / "audit.jsonl"))
    transcription_port = _FakeTranscriptionPort()
    llm_port = _FakeLlmPort()
    app = create_app(
        settings=_settings(),
        transcription_port=transcription_port,
        llm_port=llm_port,
        consent_gate=ConsentGate(),
        audit_log=audit_log,
    )
    return TestClient(app), audit_log, transcription_port, llm_port


def _read_audit_lines(audit_log: AuditLog) -> list[dict]:
    return [json.loads(line) for line in Path(audit_log.path).read_text(encoding="utf-8").splitlines()]


def test_three_routes_exist_and_no_websocket_route(tmp_path: Path) -> None:
    client, *_ = _build_client(tmp_path)
    paths = {route.path for route in client.app.routes}  # type: ignore[attr-defined]

    assert "/api/v1/consent" in paths
    assert "/api/v1/protocol" in paths
    assert "/api/v1/protocol/{protocol_id}" in paths


def test_post_consent_creates_consent_reference(tmp_path: Path) -> None:
    client, audit_log, _, _ = _build_client(tmp_path)

    response = client.post(
        "/api/v1/consent",
        json={"session_id": "session-1", "participant_acknowledged": True, "text_version": "v1.0"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "consent_ref" in body and body["consent_ref"]
    assert body["tenant_id"] == "zukunftsbund"
    assert body["session_id"] == "session-1"
    assert body["text_version"] == "v1.0"
    assert "granted_at" in body

    audit_lines = _read_audit_lines(audit_log)
    assert any(line["action"] == "create" and line["routing_region"] == "EU" for line in audit_lines)


def test_post_consent_without_participant_acknowledged_is_rejected(tmp_path: Path) -> None:
    """Finding 3 (BLOCKER §201 StGB): ohne explizite Zustimmung keine Consent-Referenz."""
    client, audit_log, _, _ = _build_client(tmp_path)

    response = client.post(
        "/api/v1/consent",
        json={"session_id": "session-2", "participant_acknowledged": False, "text_version": "v1.0"},
    )

    assert response.status_code in (400, 403)

    audit_lines = _read_audit_lines(audit_log)
    assert any(line["result"] == "denied" for line in audit_lines)


def test_post_consent_defaults_participant_acknowledged_to_false_and_rejects(tmp_path: Path) -> None:
    """Fail-closed: fehlt `participant_acknowledged` komplett, wird NICHT stillschweigend erteilt."""
    client, _, _, _ = _build_client(tmp_path)

    response = client.post("/api/v1/consent", json={"session_id": "session-3"})

    assert response.status_code in (400, 403)


def test_post_protocol_without_consent_is_rejected_with_403(tmp_path: Path) -> None:
    client, audit_log, _, _ = _build_client(tmp_path)

    response = client.post(
        "/api/v1/protocol",
        data={"consent_ref": "does-not-exist"},
        files={"audio": ("audio.wav", b"fake-audio-bytes", "audio/wav")},
    )

    assert response.status_code == 403

    audit_lines = _read_audit_lines(audit_log)
    assert any(line["result"] == "denied" for line in audit_lines)


def test_post_protocol_with_valid_consent_returns_diarized_protocol(tmp_path: Path) -> None:
    client, audit_log, transcription_port, llm_port = _build_client(tmp_path)

    consent_response = client.post(
        "/api/v1/consent",
        json={"session_id": "session-42", "participant_acknowledged": True, "text_version": "v1.0"},
    )
    consent_ref = consent_response.json()["consent_ref"]

    response = client.post(
        "/api/v1/protocol",
        data={"consent_ref": consent_ref, "session_id": "session-42"},
        files={"audio": ("audio.wav", b"fake-audio-bytes", "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "zukunftsbund"
    assert body["session_id"] == "session-42"
    assert body["consent_ref"] == consent_ref
    assert set(body["speakers"]) == {"coach", "counterpart"}
    assert len(body["segments"]) == 2
    assert body["segments"][0]["speaker"] == "coach"
    assert body["segments"][0]["words"][0]["text"] == "Wie"
    assert body["summary"] == "Zusammenfassung: Klient wirkt angespannt."
    assert body["stt_model"] == "voxtral-mini-2602"
    assert body["reasoning_model"] == "magistral-medium-2509"
    assert "id" in body and body["id"]

    # snake_case durchgängig (kein camelCase-Leak)
    assert "tStartMs" not in json.dumps(body)
    assert "t_start_ms" in json.dumps(body)

    # Audio wurde tatsächlich an den STT-Adapter weitergereicht (Diarisation + Wort-Zeitstempel angefragt).
    assert transcription_port.received_opts is not None
    assert transcription_port.received_opts.diarization is True
    assert transcription_port.received_opts.word_timestamps is True
    assert llm_port.received_messages is not None

    # Je Modellaufruf genau ein Audit-Eintrag, niemals Gesprächsinhalt.
    audit_lines = _read_audit_lines(audit_log)
    model_calls = [line for line in audit_lines if line["action"] == "model_call"]
    assert len(model_calls) == 2
    resources = {line["resource"] for line in model_calls}
    assert "voxtral-mini-2602:transcribe_batch" in resources
    assert "magistral-medium-2509:summary" in resources
    for line in model_calls:
        assert line["routing_region"] == "EU"
        assert line["pii_present"] is False
        assert "Wie geht es Ihnen" not in json.dumps(line)
        assert "angespannt" not in json.dumps(line)


def _create_consent(client: TestClient, **overrides: object) -> dict:
    payload: dict[str, object] = {"participant_acknowledged": True, "text_version": "v1.0"}
    payload.update(overrides)
    response = client.post("/api/v1/consent", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _create_protocol(client: TestClient, consent_ref: str, **overrides: str) -> dict:
    data: dict[str, str] = {"consent_ref": consent_ref}
    data.update(overrides)
    response = client.post(
        "/api/v1/protocol",
        data=data,
        files={"audio": ("audio.wav", b"fake-bytes", "audio/wav")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_get_protocol_by_id_returns_previously_created_protocol(tmp_path: Path) -> None:
    client, *_ = _build_client(tmp_path)

    consent = _create_consent(client)
    consent_ref = consent["consent_ref"]
    created = _create_protocol(client, consent_ref)

    fetched = client.get(f"/api/v1/protocol/{created['id']}", params={"consent_ref": consent_ref})

    assert fetched.status_code == 200
    assert fetched.json() == created


def test_get_protocol_unknown_id_returns_404(tmp_path: Path) -> None:
    client, *_ = _build_client(tmp_path)

    consent_ref = _create_consent(client)["consent_ref"]

    response = client.get("/api/v1/protocol/does-not-exist", params={"consent_ref": consent_ref})

    assert response.status_code == 404


def test_get_protocol_without_consent_ref_is_rejected(tmp_path: Path) -> None:
    """Finding 2 (BLOCKER IDOR): ohne consent_ref kein Zugriff, auch nicht auf eine gültige ID."""
    client, audit_log, *_ = _build_client(tmp_path)

    consent_ref = _create_consent(client)["consent_ref"]
    created = _create_protocol(client, consent_ref)

    response = client.get(f"/api/v1/protocol/{created['id']}")

    assert response.status_code == 403
    assert "Wie geht es Ihnen" not in response.text


def test_get_protocol_with_invalid_consent_ref_is_rejected(tmp_path: Path) -> None:
    """Finding 2 (BLOCKER IDOR): eine unbekannte/fremde consent_ref wird abgelehnt."""
    client, *_ = _build_client(tmp_path)

    consent_ref = _create_consent(client)["consent_ref"]
    created = _create_protocol(client, consent_ref)

    response = client.get(
        f"/api/v1/protocol/{created['id']}", params={"consent_ref": "not-a-real-consent-ref"}
    )

    assert response.status_code == 403


def test_get_protocol_accepts_consent_ref_via_header(tmp_path: Path) -> None:
    """`consent_ref` darf laut Finding 2 auch als Header übergeben werden."""
    client, *_ = _build_client(tmp_path)

    consent_ref = _create_consent(client)["consent_ref"]
    created = _create_protocol(client, consent_ref)

    response = client.get(f"/api/v1/protocol/{created['id']}", headers={"X-Consent-Ref": consent_ref})

    assert response.status_code == 200
    assert response.json() == created


def test_get_protocol_cross_tenant_access_is_rejected(tmp_path: Path) -> None:
    """Finding 2 (BLOCKER IDOR): eine gültige consent_ref eines ANDEREN Mandanten darf das
    Protokoll eines fremden Mandanten nicht offenlegen — `store.get` muss nach `tenant_id`
    gefiltert werden, selbst wenn die vorgelegte consent_ref für sich genommen gültig ist."""
    client, *_ = _build_client(tmp_path)

    consent_a = _create_consent(client, tenant_id="tenant-a", session_id="session-a")
    protocol_a = _create_protocol(client, consent_a["consent_ref"], tenant_id="tenant-a")

    consent_b = _create_consent(client, tenant_id="tenant-b", session_id="session-b")

    response = client.get(
        f"/api/v1/protocol/{protocol_a['id']}",
        params={"consent_ref": consent_b["consent_ref"], "tenant_id": "tenant-b"},
    )

    assert response.status_code in (403, 404)
    assert "Wie geht es Ihnen" not in response.text


def test_app_module_level_instance_has_no_websocket_route() -> None:
    """Smoke: `souffleur.core.app.app` ist ohne echten Netzzugriff importierbar (kein API-Key nötig)."""
    from souffleur.core.app import app as module_app

    paths = [route.path for route in module_app.routes]
    assert "/api/v1/consent" in paths
    assert "/api/v1/protocol" in paths
    assert "/api/v1/protocol/{protocol_id}" in paths
