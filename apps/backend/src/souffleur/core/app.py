"""core/app.py — FastAPI-Application-Factory (Phase 1 REST, Welle 6 + Phase 2 Live, Welle 14).

`create_app(...)` verdrahtet ConsentGate, AuditLog, `TranscriptionPort` (Default:
`voxtral_api` über die Factory aus Welle 3) und `LlmPort` (Mistral, Welle 5) zur
Phase-1-Pipeline (Welle 6) UND zusätzlich den Live-WS-Router (Welle 14: TranscriptEventBus,
TriggerRouter, ReasoningEngine, Coaching-MCP-Client). Default-Wiring liest `Settings.
from_env()` und baut die echten Adapter — Tests übergeben gemockte Ports, damit keine echten
Netzaufrufe nötig sind (Gate E1/E2). `ConsentDeniedError` wird hier global 1:1 auf HTTP 403
gemappt (Vertrag aus `core/consent.py`) — gilt für REST; der Live-WS-Router mappt denselben
Vertrag selbst auf einen WS-Close (`api/live.py`).

Der Live-Router wird ZUSÄTZLICH eingehängt (`include_router`) — die Phase-1-REST-Routen aus
Welle 6 bleiben unverändert (kein Override, kein Pfad-Konflikt: `/api/v1/*` vs. `/ws/v1/live`).
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# CORS für lokalen Browser-/Overlay-Zugriff (Web :5173, Tauri dev). Konfigurierbar via
# SOUFFLEUR_CORS_ORIGINS (kommagetrennt). Nur explizite Origins (kein Wildcard) — EU/Datenschutz.
_DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:1420,http://127.0.0.1:1420,tauri://localhost"
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("SOUFFLEUR_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]

from souffleur.adapters.llm.mistral import MistralLlmAdapter
from souffleur.adapters.mcp.coaching_mcp_client import CoachingMcpStdioClient
from souffleur.adapters.stt.factory import build_transcription_port
from souffleur.adapters.stt.voxtral_api import VoxtralApiTranscriptionPort
from souffleur.api.live import LiveDeps, build_live_router
from souffleur.api.protocol import ProtocolDeps, build_protocol_router
from souffleur.audit.audit_log import AuditLog
from souffleur.bus import InProcessTranscriptEventBus, TranscriptEventBus
from souffleur.core.consent import ConsentDeniedError, ConsentGate
from souffleur.core.reasoning import CoachingKnowledgeClient, ReasoningEngine
from souffleur.core.settings import STT_PROVIDER_VOXTRAL_API, Settings
from souffleur.ports.llm import LlmPort
from souffleur.ports.transcription import TranscriptionPort
from souffleur.trigger.router import TriggerRouter

# `packages/coaching-mcp/src` — damit `python -m coaching_mcp` (Default-MCP-Kommando) ohne
# vorherige Installation des Pakets importierbar ist (analog `apps/backend/conftest.py`).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_COACHING_MCP_DIR = _REPO_ROOT / "packages" / "coaching-mcp"
_COACHING_MCP_SRC = _COACHING_MCP_DIR / "src"

logger = logging.getLogger(__name__)


async def _aclose_if_supported(resource: Any, *, what: str) -> None:
    """Ruft `resource.aclose()` auf, falls vorhanden — best-effort, loggt statt zu crashen.

    Sowohl `CoachingKnowledgeClient` (Protocol) als auch `LlmPort` (Protocol) verlangen kein
    `aclose()` (Test-Doubles müssen es nicht implementieren) — die konkreten Default-Adapter
    (`CoachingMcpStdioClient`, `MistralLlmAdapter`) haben aber eines (Finding 10/15)."""
    aclose = getattr(resource, "aclose", None)
    if not callable(aclose):
        return
    try:
        await aclose()
    except Exception:  # noqa: BLE001 - Shutdown darf nie an einem einzelnen Resource-Close hängen
        logger.exception("Fehler beim Schließen von %s (%r) im App-Shutdown", what, resource)


def _build_lifespan(
    mcp_client: CoachingKnowledgeClient,
    llm_port: LlmPort,
) -> Any:
    """Baut den FastAPI-Lifespan-Hook (Finding 10, MCP-Zombie / Finding 15, Mistral-Leak).

    Vorher wurde `CoachingMcpStdioClient.aclose()` nirgendwo aufgerufen — der lazy gestartete
    stdio-Subprozess (Coaching-MCP-Server) blieb beim App-Shutdown als Zombie-Prozess zurück.
    Ebenso wurde der von `MistralLlmAdapter` gehaltene HTTP-Client nie geschlossen. Dieser
    Lifespan schließt beide beim Shutdown — unabhängig voneinander (ein Fehler beim einen
    verhindert nicht das Schließen des anderen).
    """

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await _aclose_if_supported(mcp_client, what="coaching_mcp_client")
            await _aclose_if_supported(llm_port, what="llm_port")

    return _lifespan


def _default_coaching_mcp_client() -> CoachingMcpStdioClient:
    import os

    env = dict(os.environ)
    existing_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{_COACHING_MCP_SRC}{os.pathsep}{existing_path}" if existing_path else str(_COACHING_MCP_SRC)
    )
    return CoachingMcpStdioClient(cwd=str(_COACHING_MCP_DIR), env=env)


def _default_live_transcription_port(
    settings: Settings, event_bus: TranscriptEventBus
) -> TranscriptionPort:
    """Live braucht denselben Adapter MIT Bus-Anbindung (Welle 12) — die Factory (Welle 3)
    kennt keinen `event_bus`-Parameter, daher hier eine dedizierte Instanz für `voxtral_api`.
    Andere Provider fallen (ohne Bus-Publish) auf die Factory zurück — dokumentierte Lücke."""
    if settings.stt_provider == STT_PROVIDER_VOXTRAL_API:
        return VoxtralApiTranscriptionPort(settings, event_bus=event_bus)
    return build_transcription_port(settings)


def create_app(
    settings: Settings | None = None,
    transcription_port: TranscriptionPort | None = None,
    llm_port: LlmPort | None = None,
    consent_gate: ConsentGate | None = None,
    audit_log: AuditLog | None = None,
    event_bus: TranscriptEventBus | None = None,
    live_transcription_port: TranscriptionPort | None = None,
    mcp_client: CoachingKnowledgeClient | None = None,
    trigger_router: TriggerRouter | None = None,
    reasoning_engine: ReasoningEngine | None = None,
) -> FastAPI:
    """Baut die FastAPI-App (Phase-1-REST + Phase-2-Live-WS). Jeder Parameter überschreibbar."""
    resolved_settings = settings or Settings.from_env()
    resolved_transcription_port = transcription_port or build_transcription_port(resolved_settings)
    resolved_llm_port = llm_port or MistralLlmAdapter(resolved_settings)
    resolved_consent_gate = consent_gate or ConsentGate()
    resolved_audit_log = audit_log or AuditLog(resolved_settings.audit_log_path)
    resolved_event_bus = event_bus or InProcessTranscriptEventBus()
    resolved_live_transcription_port = live_transcription_port or _default_live_transcription_port(
        resolved_settings, resolved_event_bus
    )
    resolved_mcp_client = mcp_client or _default_coaching_mcp_client()
    resolved_trigger_router = trigger_router or TriggerRouter(
        resolved_llm_port, resolved_settings, audit_log=resolved_audit_log
    )
    resolved_reasoning_engine = reasoning_engine or ReasoningEngine(
        resolved_llm_port,
        resolved_mcp_client,
        resolved_event_bus,
        resolved_settings,
        audit_log=resolved_audit_log,
    )

    protocol_deps = ProtocolDeps(
        settings=resolved_settings,
        transcription_port=resolved_transcription_port,
        llm_port=resolved_llm_port,
        consent_gate=resolved_consent_gate,
        audit_log=resolved_audit_log,
    )
    live_deps = LiveDeps(
        settings=resolved_settings,
        transcription_port=resolved_live_transcription_port,
        consent_gate=resolved_consent_gate,
        audit_log=resolved_audit_log,
        event_bus=resolved_event_bus,
        trigger_router=resolved_trigger_router,
        reasoning_engine=resolved_reasoning_engine,
    )

    fastapi_app = FastAPI(
        title="Souffleur AI Backend",
        version="0.1.0",
        lifespan=_build_lifespan(resolved_mcp_client, resolved_llm_port),
    )
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fastapi_app.state.protocol_deps = protocol_deps
    fastapi_app.state.live_deps = live_deps
    fastapi_app.state.deps = protocol_deps  # Rückwärtskompatibel (Welle 6: `app.state.deps`)
    fastapi_app.include_router(build_protocol_router(protocol_deps))  # Phase 1 — unverändert
    fastapi_app.include_router(build_live_router(live_deps))  # Phase 2 — zusätzlich

    @fastapi_app.exception_handler(ConsentDeniedError)
    async def _handle_consent_denied(request: Request, exc: ConsentDeniedError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    return fastapi_app


app = create_app()
