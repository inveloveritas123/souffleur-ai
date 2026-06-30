"""api/protocol.py — REST-Endpunkte der Phase-1-Pipeline (Async-Protokoll, Welle 6).

- `POST /api/v1/consent`: legt eine dokumentierte Einwilligung an, gibt eine Consent-Referenz.
- `POST /api/v1/protocol`: Audio (multipart) + Consent-Referenz -> `ConsentGate` (403 ohne
  gültige Einwilligung) -> `voxtral_api` Batch-Transkription (Diarisation + Wort-Zeitstempel)
  -> `magistral-medium-2509`-Zusammenfassung -> diarisiertes Protokoll als JSON.
- `GET /api/v1/protocol/{protocol_id}`: liest ein zuvor erzeugtes Protokoll.

Je Modellaufruf (STT-Batch, Reasoning) genau ein `AuditLog`-Eintrag (routing_region=EU,
pii_present=false — Gate E2/E4). `ConsentDeniedError` wird NICHT hier auf HTTP gemappt,
sondern propagiert zum globalen Exception-Handler in `core/app.py` (1:1 auf 403, gemäß
`core/consent.py`-Vertrag: "die Web-Schicht mappt die Exception 1:1 auf HTTP 403").
snake_case durchgängig (FastAPI/Pydantic-Feldnamen ohne Alias).

Phase-1-Scope (ARCHITECTURE.md "Phase-1-vs-Phase-2-Abgrenzung"): kein Overlay, kein
Live-Streaming, kein Trigger-Router — die Reasoning-Zusammenfassung nutzt zwar die
streamende `LlmPort`-Methode, der REST-Endpunkt konsumiert den Stream aber vollständig
serverseitig und liefert ein einziges JSON-Ergebnis (kein SSE/WebSocket in Phase 1).
"""
from __future__ import annotations

import datetime as dt
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from souffleur.audit.audit_log import AuditLog
from souffleur.core.consent import ConsentDeniedError, ConsentGate, ConsentRecord
from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage, LlmPort
from souffleur.ports.transcription import TranscriptionPort
from souffleur.ports.types import AudioRef, BatchOptions, TranscriptResult

# --- Request/Response-Schemas (snake_case, exakt zum Web-Client-Vertrag) -------------


class ConsentRequest(BaseModel):
    tenant_id: str | None = None
    session_id: str | None = None


class ConsentResponse(BaseModel):
    consent_ref: str
    tenant_id: str
    session_id: str
    granted_at: str


class WordOut(BaseModel):
    text: str
    t_start_ms: int
    t_end_ms: int


class SegmentOut(BaseModel):
    speaker: str
    text: str
    t_start_ms: int
    t_end_ms: int
    words: list[WordOut] | None = None


class ProtocolResponse(BaseModel):
    id: str
    tenant_id: str
    session_id: str
    consent_ref: str
    created_at: str
    duration_ms: int
    stt_model: str
    reasoning_model: str
    speakers: list[str]
    segments: list[SegmentOut]
    summary: str


# --- In-Memory-Protokoll-Ablage (Phase 1, keine Persistenzschicht in dieser Welle) ----


@dataclass
class ProtocolStore:
    """Hält erzeugte Protokolle in-process vor (Thread-safe append/lookup)."""

    _records: dict[str, ProtocolResponse] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def save(self, record: ProtocolResponse) -> None:
        with self._lock:
            self._records[record.id] = record

    def get(self, protocol_id: str) -> ProtocolResponse | None:
        with self._lock:
            return self._records.get(protocol_id)


# --- Dependencies-Bündel (von core/app.py verdrahtet; Tests übergeben Fakes) ----------


@dataclass
class ProtocolDeps:
    settings: Settings
    transcription_port: TranscriptionPort
    llm_port: LlmPort
    consent_gate: ConsentGate
    audit_log: AuditLog
    store: ProtocolStore = field(default_factory=ProtocolStore)


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _build_transcript_context(result: TranscriptResult) -> str:
    """Baut Klartext-Kontext fürs Reasoning-Modell — fließt NIE ins Audit-Log (Gate E2)."""
    lines = [f"{segment.speaker}: {segment.text}" for segment in result.segments]
    return "\n".join(lines)


SUMMARY_SYSTEM_PROMPT = (
    "Du bist ein Coaching-Assistent. Fasse das folgende diarisierte Coaching-Gespräch "
    "strukturiert zusammen: zentrale Themen, Einwände, vereinbarte nächste Schritte. "
    "Antworte auf Deutsch, prägnant, ohne Wertung."
)


def build_protocol_router(deps: ProtocolDeps) -> APIRouter:
    """Baut den `/api/v1`-Router gebunden an ein konkretes `ProtocolDeps`-Bündel."""
    router = APIRouter(prefix="/api/v1")

    @router.post("/consent", response_model=ConsentResponse)
    def create_consent(payload: ConsentRequest) -> ConsentResponse:
        tenant_id = payload.tenant_id or deps.settings.tenant_id
        session_id = payload.session_id or str(uuid.uuid4())
        consent_ref = str(uuid.uuid4())
        granted_at = _now_iso()

        deps.consent_gate.register(
            ConsentRecord(
                consent_ref=consent_ref,
                tenant_id=tenant_id,
                session_id=session_id,
                granted_at=granted_at,
            )
        )
        deps.audit_log.record(
            actor="api:consent",
            action="create",
            resource=f"consent:{session_id}",
            tenant_id=tenant_id,
            result="success",
            correlation_id=consent_ref,
        )
        return ConsentResponse(
            consent_ref=consent_ref,
            tenant_id=tenant_id,
            session_id=session_id,
            granted_at=granted_at,
        )

    @router.post("/protocol", response_model=ProtocolResponse)
    async def create_protocol(
        audio: UploadFile = File(...),
        consent_ref: str = Form(...),
        tenant_id: str | None = Form(None),
        session_id: str | None = Form(None),
        language: str | None = Form(None),
    ) -> ProtocolResponse:
        effective_tenant_id = tenant_id or deps.settings.tenant_id
        effective_session_id = session_id or str(uuid.uuid4())
        protocol_id = str(uuid.uuid4())

        try:
            deps.consent_gate.check(consent_ref=consent_ref, tenant_id=effective_tenant_id)
        except ConsentDeniedError:
            deps.audit_log.record(
                actor="api:protocol",
                action="read",
                resource=f"consent:{effective_session_id}",
                tenant_id=effective_tenant_id,
                result="denied",
            )
            raise  # 1:1 auf HTTP 403 gemappt durch den globalen Handler (core/app.py)

        audio_bytes = await audio.read()
        tmp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            stt_result = await deps.transcription_port.transcribe_batch(
                AudioRef(local_path=tmp_path),
                BatchOptions(diarization=True, word_timestamps=True, language=language),
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        deps.audit_log.record(
            actor="api:protocol",
            action="model_call",
            resource=f"{deps.settings.model_stt_batch}:transcribe_batch",
            tenant_id=effective_tenant_id,
            result="success",
            model=deps.settings.model_stt_batch,
            correlation_id=protocol_id,
        )

        transcript_context = _build_transcript_context(stt_result)
        summary_parts: list[str] = []
        async for delta in deps.llm_port.stream_reasoning(
            [
                ChatMessage(role="system", content=SUMMARY_SYSTEM_PROMPT),
                ChatMessage(role="user", content=transcript_context),
            ]
        ):
            summary_parts.append(delta)
        summary = "".join(summary_parts)

        deps.audit_log.record(
            actor="api:protocol",
            action="model_call",
            resource=f"{deps.settings.model_reasoning}:summary",
            tenant_id=effective_tenant_id,
            result="success",
            model=deps.settings.model_reasoning,
            correlation_id=protocol_id,
        )

        response = ProtocolResponse(
            id=protocol_id,
            tenant_id=effective_tenant_id,
            session_id=effective_session_id,
            consent_ref=consent_ref,
            created_at=_now_iso(),
            duration_ms=stt_result.duration_ms,
            stt_model=stt_result.model,
            reasoning_model=deps.settings.model_reasoning,
            speakers=stt_result.speakers,
            segments=[
                SegmentOut(
                    speaker=seg.speaker,
                    text=seg.text,
                    t_start_ms=seg.t_start_ms,
                    t_end_ms=seg.t_end_ms,
                    words=(
                        [WordOut(text=w.text, t_start_ms=w.t_start_ms, t_end_ms=w.t_end_ms) for w in seg.words]
                        if seg.words
                        else None
                    ),
                )
                for seg in stt_result.segments
            ],
            summary=summary,
        )
        deps.store.save(response)
        return response

    @router.get("/protocol/{protocol_id}", response_model=ProtocolResponse)
    def get_protocol(protocol_id: str) -> ProtocolResponse:
        record = deps.store.get(protocol_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Protokoll nicht gefunden")
        return record

    return router
