"""ReasoningEngine — Coaching-Karten erzeugen (Welle 13).

ARCHITECTURE.md: "Bei Karte holt die ReasoningEngine Wissen vom Coaching-MCP-Server und
streamt die Karte über magistral-medium-2509." Ablauf pro Trigger:
1. `trigger.fired` auf den Bus (Karten-Typ im `payload.text`, siehe `bus/event_bus.py`
   Docstring zur eingeschränkten Payload-Form).
2. Coaching-Wissen vom MCP-Server holen (`CoachingKnowledgeClient.get_coaching_knowledge`).
3. `magistral-medium-2509` streamt die Karte; jedes Text-Delta geht als `card.streamed` auf
   den Bus (Display-Schicht baut die Karte gestreamt auf).
4. `card.proposed` mit dem vollständigen Kartentext, ein Audit-Eintrag für den Modellaufruf.

Gesprächsinhalt/Kartentext fließt NIE ins Audit-Log (Gate E2) — nur Metadaten (Modell,
Ergebnis, correlation_id).
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from souffleur.audit.audit_log import AuditLog
from souffleur.bus import BusEvent, BusEventPayload, SeqCounter, TranscriptEventBus, now_ms
from souffleur.core.settings import Settings
from souffleur.ports.llm import ChatMessage, LlmPort

CARD_SYSTEM_PROMPT = (
    "Du bist ein Coaching-Copilot. Formuliere anhand des folgenden Coaching-Wissens eine "
    "kurze, unaufdringliche Hinweiskarte (max. 2-3 Sätze) für den Coach - eine Fragetechnik "
    "oder Perspektive, kein Vertriebsskript. Antworte auf Deutsch, prägnant."
)


@runtime_checkable
class CoachingKnowledgeClient(Protocol):
    """Vertrag zum Coaching-MCP-Server — `get_coaching_knowledge(card_type, query, limit)`."""

    async def get_coaching_knowledge(
        self, card_type: str, query: str | None = None, limit: int = 3
    ) -> list[dict[str, Any]]: ...


def _build_card_prompt(
    card_type: str, trigger_text: str, knowledge: list[dict[str, Any]]
) -> list[ChatMessage]:
    knowledge_lines = "\n".join(
        f"- {entry.get('title', '')}: {entry.get('guidance') or entry.get('summary', '')}"
        for entry in knowledge
    )
    user_content = (
        f"Karten-Typ: {card_type}\n"
        f"Auslösende Äußerung: {trigger_text}\n"
        f"Verfügbares Coaching-Wissen:\n{knowledge_lines or '(kein spezifisches Wissen gefunden)'}"
    )
    return [
        ChatMessage(role="system", content=CARD_SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_content),
    ]


class ReasoningEngine:
    """MCP-Wissen abrufen -> magistral-medium-2509 streamen -> Bus (`trigger.fired`/`card.*`)."""

    def __init__(
        self,
        llm_port: LlmPort,
        mcp_client: CoachingKnowledgeClient,
        event_bus: TranscriptEventBus,
        settings: Settings,
        *,
        audit_log: AuditLog | None = None,
        knowledge_limit: int = 3,
    ) -> None:
        self._llm = llm_port
        self._mcp_client = mcp_client
        self._bus = event_bus
        self._settings = settings
        self._audit_log = audit_log
        self._knowledge_limit = knowledge_limit
        self._seq = SeqCounter()

    async def handle_trigger(
        self,
        *,
        session_id: str,
        tenant_id: str,
        card_type: str,
        trigger_text: str,
        correlation_id: str,
    ) -> str:
        """Führt den vollständigen Karten-Ablauf aus; gibt den vollständigen Kartentext zurück."""
        await self._publish(
            session_id,
            tenant_id,
            "trigger.fired",
            BusEventPayload(speaker="coach", text=card_type),
            correlation_id,
        )

        knowledge = await self._mcp_client.get_coaching_knowledge(
            card_type, query=trigger_text, limit=self._knowledge_limit
        )

        messages = _build_card_prompt(card_type, trigger_text, knowledge)
        parts: list[str] = []
        async for delta in self._llm.stream_reasoning(messages):
            if not delta:
                continue
            parts.append(delta)
            await self._publish(
                session_id,
                tenant_id,
                "card.streamed",
                BusEventPayload(speaker="coach", text=delta),
                correlation_id,
            )
        card_text = "".join(parts)

        if self._audit_log is not None:
            self._audit_log.record(
                actor="reasoning_engine",
                action="model_call",
                resource=f"{self._settings.model_reasoning}:card",
                tenant_id=tenant_id,
                result="success",
                model=self._settings.model_reasoning,
                correlation_id=correlation_id,
            )

        await self._publish(
            session_id,
            tenant_id,
            "card.proposed",
            BusEventPayload(speaker="coach", text=card_text),
            correlation_id,
        )
        return card_text

    async def _publish(
        self,
        session_id: str,
        tenant_id: str,
        event_type: str,
        payload: BusEventPayload,
        correlation_id: str,
    ) -> None:
        await self._bus.publish(
            session_id,
            BusEvent(
                type=event_type,  # type: ignore[arg-type]
                session_id=session_id,
                tenant_id=tenant_id,
                seq=self._seq.next(session_id),
                ts_ms=now_ms(),
                payload=payload,
                correlation_id=correlation_id,
            ),
        )
