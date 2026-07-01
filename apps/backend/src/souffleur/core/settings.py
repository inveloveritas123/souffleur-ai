"""Zentrale Konfiguration für Souffleur AI (Welle 1 — Fundament).

Liest ausschließlich die in `.env.example` dokumentierten Umgebungsvariablen über
`os.environ` (niemals Secrets im Code, Gate D3). Die vier Modell-IDs sind als
Modul-Konstanten gepinnt (ARCHITECTURE.md Tabelle "Modell-Routing & Pinning",
Gate F1) — kein bewegliches `latest`-Tag. Ein Override aus der Umgebung wird
gelesen, aber gegen Drift validiert: enthält der Wert `latest`, wird er abgelehnt.

Single-Provider Mistral, Basis-URL ausschließlich `https://api.mistral.ai` (EU,
Paris) — Gate E1.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

# --- Gepinnte Modell-IDs (ARCHITECTURE.md, Gate F1: kein 'latest') -----------------
MODEL_STT_LIVE = "voxtral-mini-transcribe-realtime-2602"
MODEL_STT_BATCH = "voxtral-mini-2602"
MODEL_REASONING = "magistral-medium-2509"
MODEL_TRIGGER = "ministral-3b-2512"

PINNED_MODELS = (MODEL_STT_LIVE, MODEL_STT_BATCH, MODEL_REASONING, MODEL_TRIGGER)

# --- Erlaubte Werte für SOUFFLEUR_STT_PROVIDER (austauschbarer Port) ---------------
STT_PROVIDER_VOXTRAL_API = "voxtral_api"
STT_PROVIDER_VOXTRAL_LOCAL = "voxtral_local"
STT_PROVIDER_GLADIA = "gladia"
VALID_STT_PROVIDERS = (STT_PROVIDER_VOXTRAL_API, STT_PROVIDER_VOXTRAL_LOCAL, STT_PROVIDER_GLADIA)

# --- EU-Defaults (Gate E1) ----------------------------------------------------------
MISTRAL_BASE_URL_DEFAULT = "https://api.mistral.ai"
GLADIA_BASE_URL_DEFAULT = "https://api.gladia.io"  # EU (Frankreich) — zulässiger Fallback


class ModelPinError(ValueError):
    """Eine Umgebungsvariable versucht, ein bewegliches Modell-Tag zu setzen (Gate F1)."""


class SttProviderError(ValueError):
    """SOUFFLEUR_STT_PROVIDER trägt einen nicht unterstützten Wert."""


class NonEuEndpointError(ValueError):
    """MISTRAL_BASE_URL zeigt nicht auf den erzwungenen EU-Endpunkt (Gate E1)."""


_ALLOWED_MISTRAL_HOST = "api.mistral.ai"


def _is_eu_mistral_host(url: str) -> bool:
    """Exakter Host-Vergleich (kein Präfix-Vergleich) — Gate E1, BLOCKER-Fix.

    `startswith("https://api.mistral.ai")` würde `https://api.mistral.ai.attacker.example`
    fälschlich akzeptieren (der Angreifer-Host beginnt textuell mit dem erlaubten Präfix).
    `urlsplit(...).hostname` liefert stattdessen den tatsächlichen Host, gegen den exakt
    verglichen wird; zusätzlich wird `https` als Schema erzwungen (kein Downgrade).
    """
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname == _ALLOWED_MISTRAL_HOST


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _pinned(env_var: str, default: str) -> str:
    """Liest eine Modell-Env-Variable; lehnt ein bewegliches 'latest'-Tag ab."""
    value = _env(env_var, default) or default
    if "latest" in value.lower():
        raise ModelPinError(f"{env_var} darf kein bewegliches 'latest'-Tag verwenden: {value!r}")
    return value


@dataclass(frozen=True)
class Settings:
    """Vollständige Laufzeit-Konfiguration, gespiegelt aus `.env.example`."""

    # --- Mistral (Single-Provider, EU-souverän, Paris) ---
    mistral_api_key: str | None
    mistral_base_url: str

    # --- STT-Port (austauschbar; reine Config) ---
    stt_provider: str

    # --- Gepinnte Modelle (Gate F1) ---
    model_stt_live: str
    model_stt_batch: str
    model_reasoning: str
    model_trigger: str

    # --- Gladia (nur falls Live-Latenz-Fallback aktiv; EU-Endpunkt Frankreich) ---
    gladia_api_key: str | None
    gladia_base_url: str

    # --- Lokaler Voxtral-Worker (MLX, Apple Silicon; nur bei voxtral_local) ---
    voxtral_local_url: str

    # --- Coaching-MCP-Server ---
    mcp_url: str

    # --- Ports ---
    backend_port: int
    web_port: int
    mcp_port: int

    # --- Mandant / Audit / Aufbewahrung ---
    tenant_id: str
    audit_log_path: str
    retention_days: int

    # --- Consent (§201 StGB) ---
    require_consent: bool

    @classmethod
    def from_env(cls) -> Settings:
        """Baut die Settings ausschließlich aus `os.environ` (Gate D3: keine Secrets im Code)."""
        stt_provider = _env("SOUFFLEUR_STT_PROVIDER", STT_PROVIDER_VOXTRAL_API) or STT_PROVIDER_VOXTRAL_API
        if stt_provider not in VALID_STT_PROVIDERS:
            raise SttProviderError(
                f"SOUFFLEUR_STT_PROVIDER={stt_provider!r} ungültig — "
                f"erlaubt: {', '.join(VALID_STT_PROVIDERS)}"
            )

        base_url = _env("MISTRAL_BASE_URL", MISTRAL_BASE_URL_DEFAULT) or MISTRAL_BASE_URL_DEFAULT
        if not _is_eu_mistral_host(base_url):
            raise NonEuEndpointError(
                f"MISTRAL_BASE_URL muss auf https://api.mistral.ai (EU) zeigen, war: {base_url!r}"
            )

        return cls(
            mistral_api_key=_env("MISTRAL_API_KEY"),
            mistral_base_url=base_url,
            stt_provider=stt_provider,
            model_stt_live=_pinned("SOUFFLEUR_MODEL_STT_LIVE", MODEL_STT_LIVE),
            model_stt_batch=_pinned("SOUFFLEUR_MODEL_STT_BATCH", MODEL_STT_BATCH),
            model_reasoning=_pinned("SOUFFLEUR_MODEL_REASONING", MODEL_REASONING),
            model_trigger=_pinned("SOUFFLEUR_MODEL_TRIGGER", MODEL_TRIGGER),
            gladia_api_key=_env("GLADIA_API_KEY"),
            gladia_base_url=_env("GLADIA_BASE_URL", GLADIA_BASE_URL_DEFAULT) or GLADIA_BASE_URL_DEFAULT,
            voxtral_local_url=_env("SOUFFLEUR_VOXTRAL_LOCAL_URL", "http://voxtral-worker:9000")
            or "http://voxtral-worker:9000",
            mcp_url=_env("SOUFFLEUR_MCP_URL", "http://coaching-mcp:8080") or "http://coaching-mcp:8080",
            backend_port=_env_int("SOUFFLEUR_BACKEND_PORT", 8000),
            web_port=_env_int("SOUFFLEUR_WEB_PORT", 5173),
            mcp_port=_env_int("SOUFFLEUR_MCP_PORT", 8080),
            tenant_id=_env("SOUFFLEUR_TENANT_ID", "zukunftsbund") or "zukunftsbund",
            audit_log_path=_env("SOUFFLEUR_AUDIT_LOG_PATH", "./data/audit-log.jsonl")
            or "./data/audit-log.jsonl",
            retention_days=_env_int("SOUFFLEUR_RETENTION_DAYS", 30),
            require_consent=_env_bool("SOUFFLEUR_REQUIRE_CONSENT", True),
        )
