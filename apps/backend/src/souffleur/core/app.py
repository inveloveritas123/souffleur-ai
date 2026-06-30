"""core/app.py — FastAPI-Application-Factory (Welle 6, Phase-1-REST "Async-Protokoll").

`create_app(...)` verdrahtet ConsentGate, AuditLog, `TranscriptionPort` (Default:
`voxtral_api` über die Factory aus Welle 3) und `LlmPort` (Mistral, Welle 5) zur
Phase-1-Pipeline (Welle 6). Default-Wiring liest `Settings.from_env()` und baut die
echten Adapter — Tests übergeben gemockte Ports, damit keine echten Netzaufrufe
nötig sind (Gate E1/E2). `ConsentDeniedError` wird hier global 1:1 auf HTTP 403
gemappt (Vertrag aus `core/consent.py`).

Nur REST (Phase 1) — kein WebSocket/Live (Phase 2, Welle 11+).
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from souffleur.adapters.llm.mistral import MistralLlmAdapter
from souffleur.adapters.stt.factory import build_transcription_port
from souffleur.api.protocol import ProtocolDeps, build_protocol_router
from souffleur.audit.audit_log import AuditLog
from souffleur.core.consent import ConsentDeniedError, ConsentGate
from souffleur.core.settings import Settings
from souffleur.ports.llm import LlmPort
from souffleur.ports.transcription import TranscriptionPort


def create_app(
    settings: Settings | None = None,
    transcription_port: TranscriptionPort | None = None,
    llm_port: LlmPort | None = None,
    consent_gate: ConsentGate | None = None,
    audit_log: AuditLog | None = None,
) -> FastAPI:
    """Baut die Phase-1-FastAPI-App. Jeder Parameter ist überschreibbar (Tests, andere STT-Provider)."""
    resolved_settings = settings or Settings.from_env()
    resolved_transcription_port = transcription_port or build_transcription_port(resolved_settings)
    resolved_llm_port = llm_port or MistralLlmAdapter(resolved_settings)
    resolved_consent_gate = consent_gate or ConsentGate()
    resolved_audit_log = audit_log or AuditLog(resolved_settings.audit_log_path)

    deps = ProtocolDeps(
        settings=resolved_settings,
        transcription_port=resolved_transcription_port,
        llm_port=resolved_llm_port,
        consent_gate=resolved_consent_gate,
        audit_log=resolved_audit_log,
    )

    fastapi_app = FastAPI(title="Souffleur AI Backend", version="0.1.0")
    fastapi_app.state.deps = deps
    fastapi_app.include_router(build_protocol_router(deps))

    @fastapi_app.exception_handler(ConsentDeniedError)
    async def _handle_consent_denied(request: Request, exc: ConsentDeniedError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    return fastapi_app


app = create_app()
