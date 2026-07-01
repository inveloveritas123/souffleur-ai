"""Welle 5 — LlmPort und Mistral-Reasoning-/Klassifikations-Adapter.

Verifiziert gegen das installierte `mistralai`-SDK (1.10.0, per `inspect.signature`):
`client.chat.stream_async(...)` ist `async def` und liefert ein `EventStreamAsync`
(awaiten, dann `async for`); `client.chat.complete_async(...)` liefert eine
`ChatCompletionResponse` mit `choices[0].message.content`. Tests mocken den Client
vollständig — keine echten Netzaufrufe (Gate E1/E2), kein latest-Tag (Gate F1).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from souffleur.adapters.llm.mistral import MistralLlmAdapter
from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage


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


class _FakeEventStream:
    """Bildet `EventStreamAsync` nach: async-iterierbar über Chunks mit `.data.choices`."""

    def __init__(self, deltas: list[str]) -> None:
        self._deltas = deltas

    def __aiter__(self) -> _FakeEventStream:
        self._iter = iter(self._deltas)
        return self

    async def __anext__(self) -> SimpleNamespace:
        try:
            text = next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None
        choice = SimpleNamespace(delta=SimpleNamespace(content=text))
        return SimpleNamespace(data=SimpleNamespace(choices=[choice]))


def _fake_client(*, stream_deltas: list[str] | None = None, complete_text: str | None = None) -> SimpleNamespace:
    chat = SimpleNamespace()
    if stream_deltas is not None:
        chat.stream_async = AsyncMock(return_value=_FakeEventStream(stream_deltas))
    if complete_text is not None:
        message = SimpleNamespace(content=complete_text)
        choice = SimpleNamespace(message=message)
        response = SimpleNamespace(choices=[choice])
        chat.complete_async = AsyncMock(return_value=response)
    return SimpleNamespace(chat=chat)


async def _collect(aiter) -> list[str]:
    return [chunk async for chunk in aiter]


def test_stream_reasoning_uses_pinned_magistral_model_and_streams_deltas() -> None:
    client = _fake_client(stream_deltas=["Der ", "Coach ", "fragte nach."])
    adapter = MistralLlmAdapter(_settings(), client=client)
    messages = [
        ChatMessage(role="system", content="Du bist Coaching-Assistent."),
        ChatMessage(role="user", content="Fasse das Gespräch zusammen."),
    ]

    deltas = asyncio.run(_collect(adapter.stream_reasoning(messages)))

    assert deltas == ["Der ", "Coach ", "fragte nach."]
    client.chat.stream_async.assert_awaited_once()
    _, kwargs = client.chat.stream_async.call_args
    assert kwargs["model"] == "magistral-medium-2509"
    assert kwargs["messages"] == [
        {"role": "system", "content": "Du bist Coaching-Assistent."},
        {"role": "user", "content": "Fasse das Gespräch zusammen."},
    ]


def test_classify_uses_pinned_ministral_3b_model() -> None:
    client = _fake_client(complete_text="einwand")
    adapter = MistralLlmAdapter(_settings(), client=client)
    messages = [ChatMessage(role="user", content="Klassifiziere: 'Das ist mir zu teuer.'")]

    result = asyncio.run(adapter.classify(messages))

    assert result.label == "einwand"
    assert result.model == "ministral-3b-2512"
    client.chat.complete_async.assert_awaited_once()
    _, kwargs = client.chat.complete_async.call_args
    assert kwargs["model"] == "ministral-3b-2512"
    assert kwargs["messages"] == [{"role": "user", "content": "Klassifiziere: 'Das ist mir zu teuer.'"}]


def test_classify_strips_whitespace_from_label() -> None:
    client = _fake_client(complete_text="  vertiefende_frage  \n")
    adapter = MistralLlmAdapter(_settings(), client=client)

    result = asyncio.run(adapter.classify([ChatMessage(role="user", content="x")]))

    assert result.label == "vertiefende_frage"
    assert result.raw_text == "  vertiefende_frage  \n"


def test_client_is_constructed_against_eu_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeMistral:
        def __init__(self, api_key: str | None = None, server_url: str | None = None) -> None:
            captured["api_key"] = api_key
            captured["server_url"] = server_url

    monkeypatch.setattr("souffleur.adapters.llm.mistral.Mistral", _FakeMistral)

    MistralLlmAdapter(_settings())

    assert captured["server_url"] == "https://api.mistral.ai"
    assert captured["api_key"] == "test-key"


def test_aclose_closes_underlying_async_http_client() -> None:
    """Finding 15 (Leak): der `Mistral`-Client wurde nie geschlossen — `aclose()` muss den
    darunterliegenden `httpx.AsyncClient` (`sdk_configuration.async_client`) schließen."""
    async_http_client = AsyncMock()
    sdk_configuration = SimpleNamespace(async_client=async_http_client)
    client = SimpleNamespace(chat=SimpleNamespace(), sdk_configuration=sdk_configuration)
    adapter = MistralLlmAdapter(_settings(), client=client)

    asyncio.run(adapter.aclose())

    async_http_client.aclose.assert_awaited_once()


def test_aclose_is_a_noop_when_client_exposes_no_sdk_configuration() -> None:
    """Fail-safe: ein Test-Double ohne `sdk_configuration` darf `aclose()` nicht crashen."""
    client = SimpleNamespace(chat=SimpleNamespace())
    adapter = MistralLlmAdapter(_settings(), client=client)

    asyncio.run(adapter.aclose())  # darf keine Exception werfen


def test_stream_reasoning_handles_empty_or_none_delta_content() -> None:
    """Robust gegen Chunks ohne Text (z. B. nur role-Delta am Stream-Anfang)."""
    client = SimpleNamespace(chat=SimpleNamespace())

    class _StreamWithEmptyChunks:
        def __aiter__(self):
            self._items = iter([None, "", "Hallo"])
            return self

        async def __anext__(self):
            try:
                text = next(self._items)
            except StopIteration:
                raise StopAsyncIteration from None
            choice = SimpleNamespace(delta=SimpleNamespace(content=text))
            return SimpleNamespace(data=SimpleNamespace(choices=[choice]))

    client.chat.stream_async = AsyncMock(return_value=_StreamWithEmptyChunks())
    adapter = MistralLlmAdapter(_settings(), client=client)

    deltas = asyncio.run(_collect(adapter.stream_reasoning([ChatMessage(role="user", content="x")])))

    assert deltas == ["Hallo"]
