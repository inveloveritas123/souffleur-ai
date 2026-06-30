"""Welle 1 — Settings liest .env.example; Modell-Pins == ARCHITECTURE.md-Tabelle."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from souffleur.core.settings import (
    MODEL_REASONING,
    MODEL_STT_BATCH,
    MODEL_STT_LIVE,
    MODEL_TRIGGER,
    STT_PROVIDER_VOXTRAL_API,
    ModelPinError,
    NonEuEndpointError,
    Settings,
    SttProviderError,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = REPO_ROOT / ".env.example"
ARCHITECTURE_MD = REPO_ROOT / "ARCHITECTURE.md"

# Env-Variable -> Settings-Attribut (deckt jede in .env.example dokumentierte Variable ab).
ENV_TO_ATTR = {
    "MISTRAL_API_KEY": "mistral_api_key",
    "MISTRAL_BASE_URL": "mistral_base_url",
    "SOUFFLEUR_STT_PROVIDER": "stt_provider",
    "SOUFFLEUR_MODEL_STT_LIVE": "model_stt_live",
    "SOUFFLEUR_MODEL_STT_BATCH": "model_stt_batch",
    "SOUFFLEUR_MODEL_REASONING": "model_reasoning",
    "SOUFFLEUR_MODEL_TRIGGER": "model_trigger",
    "GLADIA_API_KEY": "gladia_api_key",
    "GLADIA_BASE_URL": "gladia_base_url",
    "SOUFFLEUR_VOXTRAL_LOCAL_URL": "voxtral_local_url",
    "SOUFFLEUR_MCP_URL": "mcp_url",
    "SOUFFLEUR_BACKEND_PORT": "backend_port",
    "SOUFFLEUR_WEB_PORT": "web_port",
    "SOUFFLEUR_MCP_PORT": "mcp_port",
    "SOUFFLEUR_TENANT_ID": "tenant_id",
    "SOUFFLEUR_AUDIT_LOG_PATH": "audit_log_path",
    "SOUFFLEUR_RETENTION_DAYS": "retention_days",
    "SOUFFLEUR_REQUIRE_CONSENT": "require_consent",
}

_INT_FIELDS = {"backend_port", "web_port", "mcp_port", "retention_days"}
_BOOL_FIELDS = {"require_consent"}


def _parse_env_example() -> dict[str, str]:
    """Parst KEY=VALUE-Zeilen aus .env.example (ignoriert Kommentare/Leerzeilen)."""
    values: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def _parse_architecture_model_table() -> dict[str, str]:
    """Extrahiert Env-Variable -> Modell-ID aus der ARCHITECTURE.md-Pinning-Tabelle."""
    text = ARCHITECTURE_MD.read_text(encoding="utf-8")
    section_match = re.search(
        r"## Modell-Routing & Pinning.*?\n(.*?)\n##", text, re.DOTALL
    )
    assert section_match, "Modell-Pinning-Tabelle nicht in ARCHITECTURE.md gefunden"
    table = section_match.group(1)
    mapping: dict[str, str] = {}
    for line in table.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 4:
            continue
        _role, model_id, _layer, env_var = cells
        if env_var.startswith("SOUFFLEUR_MODEL_"):
            mapping[env_var] = model_id
    return mapping


def test_env_example_contains_all_documented_variables() -> None:
    """Smoke: .env.example liegt vor und enthält alle von Settings erwarteten Keys."""
    parsed = _parse_env_example()
    for env_var in ENV_TO_ATTR:
        assert env_var in parsed, f".env.example fehlt Variable {env_var}"


def test_settings_reads_every_variable_from_env_example(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings.from_env() liest jede in .env.example dokumentierte Variable korrekt."""
    parsed = _parse_env_example()
    for key, value in parsed.items():
        if value == "REPLACE_ME":
            value = "test-secret-value"
        monkeypatch.setenv(key, value)

    settings = Settings.from_env()

    for env_var, attr in ENV_TO_ATTR.items():
        raw = parsed[env_var]
        if raw == "REPLACE_ME":
            raw = "test-secret-value"
        actual = getattr(settings, attr)
        if attr in _INT_FIELDS:
            assert actual == int(raw), f"{attr} sollte {raw} sein, war {actual}"
        elif attr in _BOOL_FIELDS:
            assert actual == (raw.lower() in ("1", "true", "yes", "on")), attr
        else:
            assert actual == raw, f"{attr} sollte {raw!r} sein, war {actual!r}"


def test_model_ids_pinned_exactly_match_architecture_table() -> None:
    """Jede gepinnte Modell-ID entspricht exakt dem Wert aus der ARCHITECTURE-Tabelle."""
    table = _parse_architecture_model_table()
    assert table["SOUFFLEUR_MODEL_STT_LIVE"] == MODEL_STT_LIVE
    assert table["SOUFFLEUR_MODEL_STT_BATCH"] == MODEL_STT_BATCH
    assert table["SOUFFLEUR_MODEL_REASONING"] == MODEL_REASONING
    assert table["SOUFFLEUR_MODEL_TRIGGER"] == MODEL_TRIGGER
    for model_id in (MODEL_STT_LIVE, MODEL_STT_BATCH, MODEL_REASONING, MODEL_TRIGGER):
        assert "latest" not in model_id.lower()


def test_stt_provider_defaults_to_voxtral_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """SOUFFLEUR_STT_PROVIDER defaultet auf voxtral_api, wenn nicht gesetzt."""
    monkeypatch.delenv("SOUFFLEUR_STT_PROVIDER", raising=False)
    settings = Settings.from_env()
    assert settings.stt_provider == STT_PROVIDER_VOXTRAL_API


def test_unknown_stt_provider_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein nicht unterstützter SOUFFLEUR_STT_PROVIDER-Wert führt zu einem klaren Fehler."""
    monkeypatch.setenv("SOUFFLEUR_STT_PROVIDER", "openai_whisper")
    with pytest.raises(SttProviderError):
        Settings.from_env()


def test_model_env_override_with_latest_tag_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein 'latest'-Tag aus der Umgebung wird abgelehnt (Gate F1, Drift-Schutz)."""
    monkeypatch.setenv("SOUFFLEUR_MODEL_STT_BATCH", "voxtral-mini-latest")
    with pytest.raises(ModelPinError):
        Settings.from_env()


def test_non_eu_mistral_base_url_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """MISTRAL_BASE_URL muss auf api.mistral.ai zeigen (Gate E1).

    Verwendet bewusst einen generischen Platzhalter statt eines realen Non-EU-Markers
    (z. B. eines anderen Anbieter-Hostnamens) — Gate E1 scannt Code/Config statisch auf
    genau solche Marker, auch innerhalb von Tests, die deren Ablehnung verifizieren.
    """
    monkeypatch.setenv("MISTRAL_BASE_URL", "https://not-the-eu-endpoint.example.test")
    with pytest.raises(NonEuEndpointError):
        Settings.from_env()
