"""Welle 11 — TranscriptEventBus: async In-Process-Pub/Sub pro Session.

Kein Netzwerk, keine echten I/O-Calls (reine asyncio-Queues) — nichts zu mocken.
"""
from __future__ import annotations

import asyncio

from souffleur.bus import (
    BusEvent,
    BusEventPayload,
    InProcessTranscriptEventBus,
    SeqCounter,
    now_ms,
)


def _event(session_id: str, seq: int, kind: str = "transcript.partial", text: str = "") -> BusEvent:
    return BusEvent(
        type=kind,  # type: ignore[arg-type]
        session_id=session_id,
        tenant_id="zukunftsbund",
        seq=seq,
        ts_ms=now_ms(),
        payload=BusEventPayload(speaker="counterpart", text=text),
        correlation_id="corr-1",
    )


def test_publish_and_subscribe_delivers_transcript_final_in_order() -> None:
    """Akzeptanz W11: publish(transcript.final) wird beim Abonnenten in Reihenfolge (seq) empfangen."""

    async def scenario() -> list[BusEvent]:
        bus = InProcessTranscriptEventBus()
        received: list[BusEvent] = []

        async def consume() -> None:
            async for event in bus.subscribe("session-1"):
                received.append(event)
                if len(received) == 2:
                    return

        consumer = asyncio.ensure_future(consume())
        await asyncio.sleep(0)  # Abonnent muss registriert sein, bevor publiziert wird

        seq = SeqCounter()
        await bus.publish(
            "session-1", _event("session-1", seq.next("session-1"), "transcript.partial", "Das Budget")
        )
        await bus.publish(
            "session-1",
            _event("session-1", seq.next("session-1"), "transcript.final", "Das Budget ist zu hoch."),
        )
        await asyncio.wait_for(consumer, timeout=1)
        return received

    received = asyncio.run(scenario())

    assert [event.seq for event in received] == [1, 2]
    assert received[0].type == "transcript.partial"
    assert received[1].type == "transcript.final"
    assert received[1].payload.text == "Das Budget ist zu hoch."


def test_subscribers_are_isolated_per_session_id() -> None:
    """Ein Abonnent von session-a bekommt keine Events von session-b."""

    async def scenario() -> tuple[list[BusEvent], list[BusEvent]]:
        bus = InProcessTranscriptEventBus()
        received_a: list[BusEvent] = []
        received_b: list[BusEvent] = []

        async def consume(session_id: str, sink: list[BusEvent]) -> None:
            async for event in bus.subscribe(session_id):
                sink.append(event)
                return

        task_a = asyncio.ensure_future(consume("session-a", received_a))
        task_b = asyncio.ensure_future(consume("session-b", received_b))
        await asyncio.sleep(0)

        await bus.publish("session-a", _event("session-a", 1, "transcript.final", "nur für a"))
        await asyncio.wait_for(task_a, timeout=1)

        await bus.close_session("session-b")
        await asyncio.wait_for(task_b, timeout=1)
        return received_a, received_b

    received_a, received_b = asyncio.run(scenario())

    assert len(received_a) == 1
    assert received_a[0].payload.text == "nur für a"
    assert received_b == []


def test_multiple_subscribers_of_same_session_both_receive_fan_out() -> None:
    """TriggerRouter UND Display-Schicht können unabhängig dieselbe Session abonnieren."""

    async def scenario() -> tuple[BusEvent, BusEvent]:
        bus = InProcessTranscriptEventBus()

        async def consume_one() -> BusEvent:
            async for event in bus.subscribe("session-fanout"):
                return event
            raise AssertionError("kein Event empfangen")

        task_1 = asyncio.ensure_future(consume_one())
        task_2 = asyncio.ensure_future(consume_one())
        await asyncio.sleep(0)

        assert bus.subscriber_count("session-fanout") == 2

        await bus.publish("session-fanout", _event("session-fanout", 1, "card.proposed", "Karte"))

        event_1 = await asyncio.wait_for(task_1, timeout=1)
        event_2 = await asyncio.wait_for(task_2, timeout=1)
        return event_1, event_2

    event_1, event_2 = asyncio.run(scenario())

    assert event_1.type == "card.proposed"
    assert event_2.type == "card.proposed"


def test_seq_counter_is_monotonic_per_session_and_independent_across_sessions() -> None:
    seq = SeqCounter()
    assert seq.next("session-1") == 1
    assert seq.next("session-1") == 2
    assert seq.next("session-2") == 1  # unabhängig je Session


def test_bus_event_payload_defaults_to_no_fields_set() -> None:
    payload = BusEventPayload()
    assert payload.speaker is None
    assert payload.text is None
    assert payload.t_start_ms is None
    assert payload.t_end_ms is None


def test_close_session_terminates_subscriber_generator() -> None:
    async def scenario() -> bool:
        bus = InProcessTranscriptEventBus()

        async def consume() -> bool:
            async for _event in bus.subscribe("session-close"):
                pass
            return True  # Generator hat sich normal beendet (kein Hang)

        task = asyncio.ensure_future(consume())
        await asyncio.sleep(0)
        await bus.close_session("session-close")
        return await asyncio.wait_for(task, timeout=1)

    assert asyncio.run(scenario()) is True
