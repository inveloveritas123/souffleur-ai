"""Unit-Tests bus/event_bus.py — In-Process-Pub/Sub, FIFO je Abonnent, Fan-Out, Session-Close."""
from __future__ import annotations

import unittest

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.bus.event_bus import (  # noqa: E402
    BusEvent,
    BusEventPayload,
    InProcessTranscriptEventBus,
    SeqCounter,
    now_ms,
)


def _event(session_id: str, seq: int, event_type: str = "transcript.final") -> BusEvent:
    return BusEvent(
        type=event_type,  # type: ignore[arg-type]
        session_id=session_id,
        tenant_id="zukunftsbund",
        seq=seq,
        ts_ms=now_ms(),
        payload=BusEventPayload(speaker="coach", text=f"event-{seq}"),
        correlation_id="corr-1",
    )


class InProcessTranscriptEventBusTest(unittest.IsolatedAsyncioTestCase):
    async def test_publish_without_subscriber_is_a_noop(self) -> None:
        bus = InProcessTranscriptEventBus()
        await bus.publish("session-1", _event("session-1", 1))  # darf nicht werfen
        self.assertEqual(bus.subscriber_count("session-1"), 0)

    async def test_subscribe_receives_events_in_publish_order(self) -> None:
        bus = InProcessTranscriptEventBus()
        received: list[BusEvent] = []

        async def consume() -> None:
            async for event in bus.subscribe("session-1"):
                received.append(event)

        import asyncio

        consumer_task = asyncio.ensure_future(consume())
        await asyncio.sleep(0)  # Subscriber registrieren lassen

        await bus.publish("session-1", _event("session-1", 1))
        await bus.publish("session-1", _event("session-1", 2))
        await bus.publish("session-1", _event("session-1", 3))
        await bus.close_session("session-1")
        await asyncio.wait_for(consumer_task, timeout=1)

        self.assertEqual([e.seq for e in received], [1, 2, 3])

    async def test_fan_out_to_multiple_subscribers(self) -> None:
        bus = InProcessTranscriptEventBus()
        import asyncio

        received_a: list[BusEvent] = []
        received_b: list[BusEvent] = []

        async def consume(sink: list[BusEvent]) -> None:
            async for event in bus.subscribe("session-1"):
                sink.append(event)

        task_a = asyncio.ensure_future(consume(received_a))
        task_b = asyncio.ensure_future(consume(received_b))
        await asyncio.sleep(0)

        self.assertEqual(bus.subscriber_count("session-1"), 2)

        await bus.publish("session-1", _event("session-1", 1))
        await bus.close_session("session-1")
        await asyncio.wait_for(task_a, timeout=1)
        await asyncio.wait_for(task_b, timeout=1)

        self.assertEqual(len(received_a), 1)
        self.assertEqual(len(received_b), 1)
        self.assertEqual(bus.subscriber_count("session-1"), 0)

    async def test_events_are_filtered_per_session(self) -> None:
        bus = InProcessTranscriptEventBus()
        import asyncio

        received: list[BusEvent] = []

        async def consume() -> None:
            async for event in bus.subscribe("session-a"):
                received.append(event)

        task = asyncio.ensure_future(consume())
        await asyncio.sleep(0)

        await bus.publish("session-b", _event("session-b", 1))  # anderer Subscriber -> ignoriert
        await bus.publish("session-a", _event("session-a", 1))
        await bus.close_session("session-a")
        await asyncio.wait_for(task, timeout=1)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].session_id, "session-a")

    async def test_subscriber_removed_from_registry_after_consumption_ends(self) -> None:
        bus = InProcessTranscriptEventBus()
        import asyncio

        async def consume() -> None:
            async for _event in bus.subscribe("session-1"):
                pass

        task = asyncio.ensure_future(consume())
        await asyncio.sleep(0)
        self.assertEqual(bus.subscriber_count("session-1"), 1)

        await bus.close_session("session-1")
        await asyncio.wait_for(task, timeout=1)
        self.assertEqual(bus.subscriber_count("session-1"), 0)


class SeqCounterTest(unittest.TestCase):
    def test_counter_increments_per_session_independently(self) -> None:
        counter = SeqCounter()
        self.assertEqual(counter.next("s1"), 1)
        self.assertEqual(counter.next("s1"), 2)
        self.assertEqual(counter.next("s2"), 1)
        self.assertEqual(counter.next("s1"), 3)


class NowMsTest(unittest.TestCase):
    def test_now_ms_is_a_positive_int(self) -> None:
        value = now_ms()
        self.assertIsInstance(value, int)
        self.assertGreater(value, 0)


if __name__ == "__main__":
    unittest.main()
