"""TranscriptEventBus — async In-Process-Pub/Sub pro Session (Welle 11).

Spiegelt `packages/shared/src/bus-event.schema.json` (ARCHITECTURE.md "Event-Bus-Schema"):
`BusEvent`/`BusEventPayload` tragen exakt die Felder des JSON-Schemas (additionalProperties
false dort — diese Dataclasses fügen keine zusätzlichen Felder hinzu). In-Process-Asyncio
hinter einem schmalen `TranscriptEventBus`-Protocol, damit Phase 3 einen Netzwerk-Adapter
(WebSocket/Redis) einsetzen kann, ohne Schicht 3/4 (TriggerRouter/ReasoningEngine/Display)
zu ändern. Reine Pub/Sub-Mechanik: keine Persistenz, kein Netzwerk hier.

`publish`/`subscribe` validieren NICHT inhaltlich, ob `seq` global monoton ist — mehrere
Producer (STT-Adapter, TriggerRouter, ReasoningEngine) können unabhängig voneinander
Sequenzen führen (siehe `SeqCounter`). Die Bus-Garantie ist FIFO-Zustellung je Abonnent in
Publish-Reihenfolge, nicht eine bus-weite Sequenznummer.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

BusEventType = Literal[
    "transcript.partial",
    "transcript.final",
    "trigger.fired",
    "card.proposed",
    "card.streamed",
    "session.closed",
]

BusEventSpeaker = Literal["coach", "counterpart"]


@dataclass(frozen=True)
class BusEventPayload:
    """Optionale Nutzdaten — Felder exakt gemäß `bus-event.schema.json` `payload`."""

    speaker: BusEventSpeaker | None = None
    text: str | None = None
    t_start_ms: int | None = None
    t_end_ms: int | None = None


@dataclass(frozen=True)
class BusEvent:
    """Eine Bus-Nachricht — Felder exakt gemäß `packages/shared/src/bus-event.schema.json`."""

    type: BusEventType
    session_id: str
    tenant_id: str
    seq: int
    ts_ms: int
    payload: BusEventPayload
    correlation_id: str


@runtime_checkable
class TranscriptEventBus(Protocol):
    """Schmales Interface — ein Phase-3-Netzwerk-Adapter kann dasselbe Protocol erfüllen."""

    async def publish(self, session_id: str, event: BusEvent) -> None: ...

    def subscribe(self, session_id: str) -> AsyncIterator[BusEvent]: ...


def now_ms() -> int:
    """Aktuelle Zeit in Millisekunden (UTC) — für `BusEvent.ts_ms`."""
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


class SeqCounter:
    """Kleiner monotoner Zähler je Session — für Producer, die `BusEvent.seq` brauchen.

    Jede Producer-Komponente (STT-Live-Adapter, TriggerRouter, ReasoningEngine) führt
    ihre eigene Sequenz; der Bus selbst erzwingt keine globale Sequenz über Producer hinweg.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)

    def next(self, session_id: str) -> int:
        self._counters[session_id] += 1
        return self._counters[session_id]


_CLOSE_SENTINEL: Any = object()


class InProcessTranscriptEventBus:
    """Default-`TranscriptEventBus`: eine `asyncio.Queue` je Abonnent, gefiltert pro `session_id`.

    Fan-out: mehrere `subscribe()`-Aufrufe für dieselbe `session_id` erhalten je eine eigene
    Queue und damit alle dieselben Events (TriggerRouter UND Display-Schicht können parallel
    abonnieren). `publish` ist FIFO je Queue — ein Abonnent empfängt Events exakt in der
    Reihenfolge, in der sie publiziert wurden.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[Any]]] = defaultdict(list)

    async def publish(self, session_id: str, event: BusEvent) -> None:
        for queue in list(self._subscribers.get(session_id, ())):
            await queue.put(event)

    def subscribe(self, session_id: str) -> AsyncIterator[BusEvent]:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._subscribers[session_id].append(queue)
        return self._consume(session_id, queue)

    async def _consume(self, session_id: str, queue: asyncio.Queue[Any]) -> AsyncIterator[BusEvent]:
        try:
            while True:
                item = await queue.get()
                if item is _CLOSE_SENTINEL:
                    break
                yield item
        finally:
            subscribers = self._subscribers.get(session_id)
            if subscribers is not None and queue in subscribers:
                subscribers.remove(queue)

    async def close_session(self, session_id: str) -> None:
        """Beendet alle offenen Abonnements einer Session (z. B. nach `session.closed`)."""
        for queue in list(self._subscribers.get(session_id, ())):
            await queue.put(_CLOSE_SENTINEL)

    def subscriber_count(self, session_id: str) -> int:
        """Hilfsmethode für Tests/Diagnose — Anzahl aktiver Abonnenten einer Session."""
        return len(self._subscribers.get(session_id, ()))
