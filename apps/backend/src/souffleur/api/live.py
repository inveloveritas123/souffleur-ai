"""api/live.py — WebSocket-API für Live-Coaching (Phase 2, Welle 14).

Ablauf je Verbindung (`/ws/v1/live`):
1. Client verbindet, sendet als erste Text-Nachricht ein JSON-Handshake:
   `{"type":"start","tenant_id":...,"session_id":...,"consent_ref":...,"sample_rate":16000,
   "language":...}`.
2. `ConsentGate.check(...)` — derselbe Vertrag wie Phase 1 (`core/consent.py`,
   `api/protocol.py`): ohne gültige Einwilligung `{"type":"error",...}` + Close (4403), ein
   Audit-Eintrag `result="denied"`. Mit gültiger Einwilligung geht es weiter.
3. `TranscriptionPort.open_stream(session)` — Dual-Source (`channels=2`, Welle 12); ein
   Audit-Eintrag für den STT-Live-Modellaufruf.
4. Drei nebenläufige Schleifen bis Verbindungsende:
   - **Empfang**: Client-Audio-Frames (bytes) -> `push_audio`; Text `{"type":"stop"}` beendet.
   - **STT-Events**: `events(handle)` treibt den `TriggerRouter` (nur bei `kind=="final"`);
     bei Trigger `ReasoningEngine.handle_trigger(...)`. Der STT-Adapter publiziert
     `transcript.partial`/`transcript.final` bereits selbst auf den Bus (Welle 12) — dieser
     Loop liest dieselben Events zusätzlich, um den Trigger zu treiben.
   - **Bus-Weiterleitung**: alles, was für diese Session auf dem Bus erscheint
     (`transcript.*` vom Adapter, `trigger.fired`/`card.*` von der ReasoningEngine), geht 1:1
     als JSON an den Client — das ist der einzige Pfad, über den Transkript-/Karten-Events den
     Client erreichen (kein doppeltes Publizieren durch diesen Router).
5. Verbindungsende: `close_stream(handle)`, `session.closed` auf den Bus, Bus-Session schließen
   (beendet die Weiterleitungsschleife über den Close-Sentinel des Bus, kein Cancel nötig).

Phase-1-REST (`api/protocol.py`) bleibt unverändert — dieser Router wird zusätzlich in
`core/app.py` eingehängt, keine bestehende Route wird überschrieben.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from souffleur.adapters.capture import DUAL_SOURCE_CHANNELS
from souffleur.audit.audit_log import AuditLog
from souffleur.bus import BusEvent, BusEventPayload, TranscriptEventBus, now_ms
from souffleur.core.consent import ConsentDeniedError, ConsentGate
from souffleur.core.reasoning import ReasoningEngine
from souffleur.core.settings import Settings
from souffleur.ports.transcription import TranscriptionPort
from souffleur.ports.types import SessionContext
from souffleur.trigger.router import TriggerRouter

LIVE_WS_PATH = "/ws/v1/live"

logger = logging.getLogger(__name__)


@dataclass
class LiveDeps:
    """Dependency-Bündel für den Live-Router (von `core/app.py` verdrahtet, Tests übergeben Fakes)."""

    settings: Settings
    transcription_port: TranscriptionPort
    consent_gate: ConsentGate
    audit_log: AuditLog
    event_bus: TranscriptEventBus
    trigger_router: TriggerRouter
    reasoning_engine: ReasoningEngine


def _bus_event_to_json(event: BusEvent) -> dict[str, Any]:
    return {
        "type": event.type,
        "session_id": event.session_id,
        "tenant_id": event.tenant_id,
        "seq": event.seq,
        "ts_ms": event.ts_ms,
        "payload": {
            "speaker": event.payload.speaker,
            "text": event.payload.text,
            "t_start_ms": event.payload.t_start_ms,
            "t_end_ms": event.payload.t_end_ms,
        },
        "correlation_id": event.correlation_id,
    }


def build_live_router(deps: LiveDeps) -> APIRouter:
    """Baut den Live-WS-Router gebunden an ein konkretes `LiveDeps`-Bündel."""
    router = APIRouter()

    @router.websocket(LIVE_WS_PATH)
    async def live_endpoint(websocket: WebSocket) -> None:  # noqa: C901 - ein Verbindungslebenszyklus
        await websocket.accept()

        try:
            start_raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return

        try:
            start_message = json.loads(start_raw)
        except json.JSONDecodeError:
            await websocket.send_json(
                {"type": "error", "detail": "Ungültige Start-Nachricht (JSON erwartet)"}
            )
            await websocket.close(code=4400)
            return

        tenant_id = start_message.get("tenant_id") or deps.settings.tenant_id
        session_id = start_message.get("session_id") or str(uuid.uuid4())
        consent_ref = start_message.get("consent_ref")
        sample_rate = int(start_message.get("sample_rate") or 16000)
        language = start_message.get("language")

        try:
            deps.consent_gate.check(consent_ref=consent_ref, tenant_id=tenant_id)
        except ConsentDeniedError as exc:
            deps.audit_log.record(
                actor="api:live",
                action="read",
                resource=f"consent:{session_id}",
                tenant_id=tenant_id,
                result="denied",
            )
            await websocket.send_json({"type": "error", "detail": exc.message})
            await websocket.close(code=4403)
            return

        session = SessionContext(
            tenant_id=tenant_id,
            session_id=session_id,
            consent_ref=consent_ref,
            sample_rate=sample_rate,
            channels=DUAL_SOURCE_CHANNELS,
            language=language,
        )

        handle = await deps.transcription_port.open_stream(session)
        deps.audit_log.record(
            actor="api:live",
            action="model_call",
            resource=f"{deps.settings.model_stt_live}:open_stream",
            tenant_id=tenant_id,
            result="success",
            model=deps.settings.model_stt_live,
            correlation_id=handle.correlation_id,
        )

        async def receive_loop() -> None:
            try:
                while True:
                    message = await websocket.receive()
                    if message.get("type") == "websocket.disconnect":
                        return
                    data = message.get("bytes")
                    if data is not None:
                        await deps.transcription_port.push_audio(handle, data)
                        continue
                    text = message.get("text")
                    if text is None:
                        continue
                    try:
                        control = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    if control.get("type") == "stop":
                        return
            except WebSocketDisconnect:
                return

        async def stt_events_loop() -> None:
            # Finding 9 (Live-Pipeline stirbt still): `contextlib.suppress(Exception)` durfte
            # NIE die ganze Schleife umschließen — ein einzelner Trigger-/MCP-/LLM-Fehler bei
            # EINEM Segment brach die gesamte `async for`-Iteration ab und damit endete die
            # Kartenpipeline für den Rest der Session lautlos. Jetzt fängt try/except NUR die
            # Verarbeitung EINES Segments; ein Fehler wird geloggt, das Segment übersprungen,
            # die Schleife läuft für alle folgenden Segmente unbeeinträchtigt weiter.
            async for event in deps.transcription_port.events(handle):
                if event.kind != "final":
                    continue
                correlation_id = str(uuid.uuid4())
                try:
                    decision = await deps.trigger_router.decide(
                        session_id=session_id,
                        tenant_id=tenant_id,
                        text=event.text,
                        correlation_id=correlation_id,
                    )
                    if decision.fire and decision.card_type is not None:
                        await deps.reasoning_engine.handle_trigger(
                            session_id=session_id,
                            tenant_id=tenant_id,
                            card_type=decision.card_type,
                            trigger_text=event.text,
                            correlation_id=correlation_id,
                        )
                except Exception:  # noqa: BLE001 - bewusst breit: ein Segment darf die Session nie killen
                    logger.exception(
                        "stt_events_loop: Trigger-/Reasoning-Fehler bei Segment übersprungen "
                        "(session_id=%s, correlation_id=%s)",
                        session_id,
                        correlation_id,
                    )
                    continue

        async def bus_forward_loop() -> None:
            with contextlib.suppress(Exception):
                async for bus_event in deps.event_bus.subscribe(session_id):
                    await websocket.send_json(_bus_event_to_json(bus_event))

        forward_task = asyncio.ensure_future(bus_forward_loop())
        try:
            await asyncio.gather(receive_loop(), stt_events_loop())
        finally:
            with contextlib.suppress(Exception):
                await deps.transcription_port.close_stream(handle)
            # Finding 15 (Leak): ohne das wächst `TriggerRouter._last_fired_at_ms` unbegrenzt
            # über die Prozesslaufzeit — jede Session, die je eine Karte auslöste, bliebe für
            # immer im Cooldown-Dict. `getattr`-Guard: Test-Doubles für `trigger_router` müssen
            # keine echte `TriggerRouter`-Instanz sein und implementieren `forget_session`
            # eventuell nicht — best-effort, kein Hard-Requirement des `decide()`-Vertrags.
            forget_session = getattr(deps.trigger_router, "forget_session", None)
            if callable(forget_session):
                with contextlib.suppress(Exception):
                    forget_session(session_id)
            await deps.event_bus.publish(
                session_id,
                BusEvent(
                    type="session.closed",
                    session_id=session_id,
                    tenant_id=tenant_id,
                    seq=0,
                    ts_ms=now_ms(),
                    payload=BusEventPayload(),
                    correlation_id=handle.correlation_id,
                ),
            )
            await deps.event_bus.close_session(session_id)
            with contextlib.suppress(Exception):
                await asyncio.wait_for(forward_task, timeout=1)
            with contextlib.suppress(Exception):
                await websocket.close()

    return router
