"""Unit-Tests adapters/llm/mistral.py — MistralLlmAdapter gegen einen gemockten SDK-Client.

Kein echter Netzaufruf: `client` wird per Dependency-Injection durch ein Fake ersetzt, das
nur die Teilmenge von `mistralai.Mistral` nachbildet, die dieser Adapter tatsächlich nutzt
(`chat.stream_async`/`chat.complete_async`, verifiziertes Antwortformat aus dem Modul-Docstring).
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from _pathfix import ensure_import_paths

ensure_import_paths()

from _test_helpers import default_settings  # noqa: E402
from souffleur.adapters.llm.mistral import MistralLlmAdapter, _content_to_text  # noqa: E402
from souffleur.ports.llm import ChatMessage  # noqa: E402


@dataclass
class _Delta:
    content: Any


@dataclass
class _Choice:
    delta: _Delta | None = None
    message: Any = None


@dataclass
class _StreamEventData:
    choices: list[_Choice]


@dataclass
class _StreamEvent:
    data: _StreamEventData


@dataclass
class _CompleteResponse:
    choices: list[_Choice]


class _FakeStreamAsync:
    """Async-iterierbar über vorgegebene Chunks — steht für `EventStreamAsync`."""

    def __init__(self, events: list[_StreamEvent]) -> None:
        self._events = events

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for event in self._events:
            yield event


class _FakeChat:
    def __init__(self, stream_events: list[_StreamEvent], complete_response: _CompleteResponse) -> None:
        self._stream_events = stream_events
        self._complete_response = complete_response
        self.stream_calls: list[dict[str, Any]] = []
        self.complete_calls: list[dict[str, Any]] = []

    async def stream_async(self, *, model: str, messages: list[dict[str, Any]]) -> _FakeStreamAsync:
        self.stream_calls.append({"model": model, "messages": messages})
        return _FakeStreamAsync(self._stream_events)

    async def complete_async(self, *, model: str, messages: list[dict[str, Any]]) -> _CompleteResponse:
        self.complete_calls.append({"model": model, "messages": messages})
        return self._complete_response


class _FakeMistralClient:
    def __init__(self, chat: _FakeChat) -> None:
        self.chat = chat


class ContentToTextTest(unittest.TestCase):
    def test_none_becomes_empty_string(self) -> None:
        self.assertEqual(_content_to_text(None), "")

    def test_plain_string_passthrough(self) -> None:
        self.assertEqual(_content_to_text("Hallo"), "Hallo")

    def test_list_of_dict_chunks_joined(self) -> None:
        self.assertEqual(_content_to_text([{"text": "A"}, {"text": "B"}]), "AB")

    def test_list_of_object_chunks_joined(self) -> None:
        class _Chunk:
            def __init__(self, text: str) -> None:
                self.text = text

        self.assertEqual(_content_to_text([_Chunk("A"), _Chunk("B")]), "AB")

    def test_falsy_chunk_text_is_skipped(self) -> None:
        self.assertEqual(_content_to_text([{"text": ""}, {"text": "B"}]), "B")


class MistralLlmAdapterStreamReasoningTest(unittest.IsolatedAsyncioTestCase):
    async def test_streams_text_deltas_and_uses_pinned_reasoning_model(self) -> None:
        events = [
            _StreamEvent(_StreamEventData([_Choice(delta=_Delta(content="Hallo "))])),
            _StreamEvent(_StreamEventData([_Choice(delta=_Delta(content="Welt."))])),
            _StreamEvent(_StreamEventData([_Choice(delta=_Delta(content=None))])),  # skip
            _StreamEvent(_StreamEventData(choices=[])),  # skip: keine choices
        ]
        chat = _FakeChat(stream_events=events, complete_response=_CompleteResponse(choices=[]))
        settings = default_settings()
        adapter = MistralLlmAdapter(settings, client=_FakeMistralClient(chat))  # type: ignore[arg-type]

        deltas = [delta async for delta in adapter.stream_reasoning([ChatMessage(role="user", content="Hi")])]

        self.assertEqual(deltas, ["Hallo ", "Welt."])
        self.assertEqual(chat.stream_calls[0]["model"], settings.model_reasoning)
        self.assertEqual(chat.stream_calls[0]["messages"], [{"role": "user", "content": "Hi"}])


class MistralLlmAdapterClassifyTest(unittest.IsolatedAsyncioTestCase):
    async def test_classify_uses_pinned_trigger_model_and_strips_label(self) -> None:
        response = _CompleteResponse(choices=[_Choice(message=_Delta(content="  objection  "))])
        chat = _FakeChat(stream_events=[], complete_response=response)
        settings = default_settings()
        adapter = MistralLlmAdapter(settings, client=_FakeMistralClient(chat))  # type: ignore[arg-type]

        result = await adapter.classify(
            [ChatMessage(role="system", content="..."), ChatMessage(role="user", content="Text")]
        )

        self.assertEqual(result.label, "objection")
        self.assertEqual(result.raw_text, "  objection  ")
        self.assertEqual(result.model, settings.model_trigger)
        self.assertEqual(chat.complete_calls[0]["model"], settings.model_trigger)

    async def test_classify_with_no_choices_returns_empty_label(self) -> None:
        chat = _FakeChat(stream_events=[], complete_response=_CompleteResponse(choices=[]))
        adapter = MistralLlmAdapter(default_settings(), client=_FakeMistralClient(chat))  # type: ignore[arg-type]

        result = await adapter.classify([ChatMessage(role="user", content="Text")])

        self.assertEqual(result.label, "")


class MistralLlmAdapterDefaultClientTest(unittest.TestCase):
    def test_without_injected_client_builds_a_real_mistral_client(self) -> None:
        from mistralai import Mistral

        adapter = MistralLlmAdapter(default_settings())
        self.assertIsInstance(adapter._client, Mistral)


if __name__ == "__main__":
    unittest.main()
