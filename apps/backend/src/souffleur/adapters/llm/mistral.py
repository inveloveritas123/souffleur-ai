"""adapters/llm/mistral — LlmPort-Implementierung über Mistral (Welle 5).

EU-Routing erzwungen (Gate E1): der `Mistral`-Client wird ausschließlich gegen
`settings.mistral_base_url` (gepinnt auf `https://api.mistral.ai`) konstruiert.
Modelle gepinnt aus Settings (Gate F1): `stream_reasoning` nutzt
`settings.model_reasoning` (magistral-medium-2509), `classify` nutzt
`settings.model_trigger` (ministral-3b-2512) — kein `-latest`-Tag, kein
hartcodierter Modellname außerhalb der Settings.

Verifiziert gegen das installierte `mistralai==1.10.0` (per `inspect.signature`):
`chat.stream_async`/`chat.complete_async` sind `async def` und müssen awaitet werden;
`stream_async` liefert danach ein `EventStreamAsync` (`async for` über Chunks mit
`.data.choices[0].delta.content`), `complete_async` liefert eine
`ChatCompletionResponse` (`.choices[0].message.content`). `content` kann laut SDK-Typ
ein `str` ODER eine Liste von `ContentChunk`s sein — `_content_to_text` behandelt
beide Fälle defensiv.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

from mistralai import Mistral
from mistralai.models import ChatCompletionStreamRequestMessagesTypedDict, MessagesTypedDict

from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage, ClassificationResult

# `role` ist zur Laufzeit dynamisch (system/user/assistant) und damit für mypy nicht
# strukturell auf die Discriminated-Union der SDK-TypedDicts prüfbar — die `cast`-Aufrufe
# unten dokumentieren, dass die Form (role+content) absichtlich exakt dem Cheatsheet-Vertrag
# entspricht (verifiziert per `inspect.signature` gegen `mistralai==1.10.0`).


def _to_complete_messages(messages: list[ChatMessage]) -> list[MessagesTypedDict]:
    return cast(
        "list[MessagesTypedDict]", [{"role": m.role, "content": m.content} for m in messages]
    )


def _to_stream_messages(
    messages: list[ChatMessage],
) -> list[ChatCompletionStreamRequestMessagesTypedDict]:
    return cast(
        "list[ChatCompletionStreamRequestMessagesTypedDict]",
        [{"role": m.role, "content": m.content} for m in messages],
    )


def _content_to_text(content: Any) -> str:
    """Wandelt `DeltaMessage.content`/`AssistantMessage.content` defensiv in Text um."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for chunk in content:
        text = chunk.get("text") if isinstance(chunk, dict) else getattr(chunk, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


class MistralLlmAdapter:
    """LlmPort-Implementierung: Reasoning streamend (magistral), Klassifikation billig (ministral-3b)."""

    def __init__(self, settings: Settings, client: Mistral | None = None) -> None:
        self._settings = settings
        self._client = client or Mistral(
            api_key=settings.mistral_api_key, server_url=settings.mistral_base_url
        )

    async def stream_reasoning(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        stream = await self._client.chat.stream_async(
            model=self._settings.model_reasoning,
            messages=_to_stream_messages(messages),
        )
        async for event in stream:
            choices = getattr(event.data, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            text = _content_to_text(getattr(delta, "content", None) if delta else None)
            if text:
                yield text

    async def classify(self, messages: list[ChatMessage]) -> ClassificationResult:
        response = await self._client.chat.complete_async(
            model=self._settings.model_trigger,
            messages=_to_complete_messages(messages),
        )
        choices = getattr(response, "choices", None) or []
        message = getattr(choices[0], "message", None) if choices else None
        raw_text = _content_to_text(getattr(message, "content", None) if message else None)
        return ClassificationResult(
            label=raw_text.strip(), raw_text=raw_text, model=self._settings.model_trigger
        )
