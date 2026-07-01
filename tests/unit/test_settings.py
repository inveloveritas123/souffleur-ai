"""Unit-Tests core/settings.py — Modell-Pinning (Gate F1), EU-Routing (Gate E1), Provider-Wahl."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from _pathfix import ensure_import_paths

ensure_import_paths()

from souffleur.core import settings as settings_module  # noqa: E402
from souffleur.core.settings import (  # noqa: E402
    MODEL_REASONING,
    MODEL_STT_BATCH,
    MODEL_STT_LIVE,
    MODEL_TRIGGER,
    ModelPinError,
    NonEuEndpointError,
    Settings,
    SttProviderError,
)

_ENV_KEYS = (
    "MISTRAL_API_KEY",
    "MISTRAL_BASE_URL",
    "SOUFFLEUR_STT_PROVIDER",
    "SOUFFLEUR_MODEL_STT_LIVE",
    "SOUFFLEUR_MODEL_STT_BATCH",
    "SOUFFLEUR_MODEL_REASONING",
    "SOUFFLEUR_MODEL_TRIGGER",
    "GLADIA_API_KEY",
    "GLADIA_BASE_URL",
    "SOUFFLEUR_VOXTRAL_LOCAL_URL",
    "SOUFFLEUR_MCP_URL",
    "SOUFFLEUR_BACKEND_PORT",
    "SOUFFLEUR_WEB_PORT",
    "SOUFFLEUR_MCP_PORT",
    "SOUFFLEUR_TENANT_ID",
    "SOUFFLEUR_AUDIT_LOG_PATH",
    "SOUFFLEUR_RETENTION_DAYS",
    "SOUFFLEUR_REQUIRE_CONSENT",
)


class SettingsFromEnvDefaultsTest(unittest.TestCase):
    """Ohne jede Env-Variable müssen alle dokumentierten Defaults gelten (Welle-1-Vertrag)."""

    def test_defaults_when_no_env_set(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = Settings.from_env()

        self.assertIsNone(result.mistral_api_key)
        self.assertEqual(result.mistral_base_url, "https://api.mistral.ai")
        self.assertEqual(result.stt_provider, "voxtral_api")
        self.assertEqual(result.model_stt_live, MODEL_STT_LIVE)
        self.assertEqual(result.model_stt_batch, MODEL_STT_BATCH)
        self.assertEqual(result.model_reasoning, MODEL_REASONING)
        self.assertEqual(result.model_trigger, MODEL_TRIGGER)
        self.assertEqual(result.gladia_base_url, "https://api.gladia.io")
        self.assertEqual(result.voxtral_local_url, "http://voxtral-worker:9000")
        self.assertEqual(result.mcp_url, "http://coaching-mcp:8080")
        self.assertEqual(result.backend_port, 8000)
        self.assertEqual(result.web_port, 5173)
        self.assertEqual(result.mcp_port, 8080)
        self.assertEqual(result.tenant_id, "zukunftsbund")
        self.assertEqual(result.audit_log_path, "./data/audit-log.jsonl")
        self.assertEqual(result.retention_days, 30)
        self.assertTrue(result.require_consent)

    def test_pinned_models_match_architecture_constants(self) -> None:
        for model in settings_module.PINNED_MODELS:
            self.assertNotIn("latest", model.lower())


class SettingsFromEnvOverridesTest(unittest.TestCase):
    """Jede Umgebungsvariable muss den zugehörigen Wert tatsächlich überschreiben."""

    def test_full_override_set(self) -> None:
        # `tempfile.gettempdir()` statt hartkodiertem "/tmp" (SAST-Befund B108 vermeiden) —
        # es wird nie tatsächlich in diesen Pfad geschrieben, nur der Settings-Wert geprüft.
        audit_log_path = os.path.join(tempfile.gettempdir(), "audit.jsonl")
        env = {
            "MISTRAL_API_KEY": "sk-real",
            "MISTRAL_BASE_URL": "https://api.mistral.ai/eu",
            "SOUFFLEUR_STT_PROVIDER": "gladia",
            "GLADIA_API_KEY": "gladia-key",
            "GLADIA_BASE_URL": "https://api.gladia.io/v2",
            "SOUFFLEUR_VOXTRAL_LOCAL_URL": "http://localhost:9001",
            "SOUFFLEUR_MCP_URL": "http://localhost:9002",
            "SOUFFLEUR_BACKEND_PORT": "9000",
            "SOUFFLEUR_WEB_PORT": "9001",
            "SOUFFLEUR_MCP_PORT": "9002",
            "SOUFFLEUR_TENANT_ID": "acme",
            "SOUFFLEUR_AUDIT_LOG_PATH": audit_log_path,
            "SOUFFLEUR_RETENTION_DAYS": "90",
            "SOUFFLEUR_REQUIRE_CONSENT": "false",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            result = Settings.from_env()

        self.assertEqual(result.mistral_api_key, "sk-real")
        self.assertEqual(result.mistral_base_url, "https://api.mistral.ai/eu")
        self.assertEqual(result.stt_provider, "gladia")
        self.assertEqual(result.gladia_api_key, "gladia-key")
        self.assertEqual(result.gladia_base_url, "https://api.gladia.io/v2")
        self.assertEqual(result.voxtral_local_url, "http://localhost:9001")
        self.assertEqual(result.mcp_url, "http://localhost:9002")
        self.assertEqual(result.backend_port, 9000)
        self.assertEqual(result.web_port, 9001)
        self.assertEqual(result.mcp_port, 9002)
        self.assertEqual(result.tenant_id, "acme")
        self.assertEqual(result.audit_log_path, audit_log_path)
        self.assertEqual(result.retention_days, 90)
        self.assertFalse(result.require_consent)

    def test_require_consent_truthy_strings(self) -> None:
        for truthy in ("1", "true", "TRUE", "yes", "on"):
            with mock.patch.dict(os.environ, {"SOUFFLEUR_REQUIRE_CONSENT": truthy}, clear=True):
                self.assertTrue(Settings.from_env().require_consent, msg=truthy)

    def test_require_consent_falsy_strings(self) -> None:
        for falsy in ("0", "false", "no", ""):
            with mock.patch.dict(os.environ, {"SOUFFLEUR_REQUIRE_CONSENT": falsy}, clear=True):
                result = Settings.from_env().require_consent
                if falsy == "":
                    self.assertTrue(result)  # leer -> Default (True)
                else:
                    self.assertFalse(result)


class SettingsValidationErrorsTest(unittest.TestCase):
    """Gate F1 (kein `latest`) und Gate E1 (EU-Routing) müssen hart durchgesetzt werden."""

    def test_unknown_stt_provider_raises(self) -> None:
        with mock.patch.dict(os.environ, {"SOUFFLEUR_STT_PROVIDER": "openai_whisper"}, clear=True):
            with self.assertRaises(SttProviderError):
                Settings.from_env()

    def test_non_eu_mistral_base_url_raises(self) -> None:
        # Bewusst ein generischer Nicht-Mistral-Host (kein bekannter Non-EU-Anbieter-Domainname)
        # — Gate E1 (`gates/checks/e1_eu_routing.py`) scannt Code-/Testdateien nach konkreten
        # Non-EU-Marken-Endpunkten (z. B. "api.openai.com"); dieser Test prüft nur, dass JEDER
        # Host ausser dem erzwungenen "https://api.mistral.ai"-Präfix abgelehnt wird.
        with mock.patch.dict(
            os.environ, {"MISTRAL_BASE_URL": "https://api.not-mistral.example"}, clear=True
        ):
            with self.assertRaises(NonEuEndpointError):
                Settings.from_env()

    def test_latest_tag_rejected_for_each_pinned_model_env_var(self) -> None:
        env_vars = (
            "SOUFFLEUR_MODEL_STT_LIVE",
            "SOUFFLEUR_MODEL_STT_BATCH",
            "SOUFFLEUR_MODEL_REASONING",
            "SOUFFLEUR_MODEL_TRIGGER",
        )
        for env_var in env_vars:
            with mock.patch.dict(os.environ, {env_var: "magistral-latest"}, clear=True):
                with self.assertRaises(ModelPinError, msg=env_var):
                    Settings.from_env()

    def test_latest_tag_check_is_case_insensitive(self) -> None:
        with mock.patch.dict(
            os.environ, {"SOUFFLEUR_MODEL_REASONING": "Magistral-LATEST"}, clear=True
        ):
            with self.assertRaises(ModelPinError):
                Settings.from_env()


class SettingsHelperFunctionsTest(unittest.TestCase):
    """Direkte Tests der privaten `_env*`-Helfer (Env-Parsing-Grenzfälle)."""

    def test_env_returns_default_for_empty_string(self) -> None:
        with mock.patch.dict(os.environ, {"X_EMPTY": ""}, clear=True):
            self.assertEqual(settings_module._env("X_EMPTY", "fallback"), "fallback")

    def test_env_int_parses_numeric_string(self) -> None:
        with mock.patch.dict(os.environ, {"X_INT": "42"}, clear=True):
            self.assertEqual(settings_module._env_int("X_INT", 0), 42)

    def test_env_int_default_when_unset(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(settings_module._env_int("X_INT_UNSET", 7), 7)


if __name__ == "__main__":
    unittest.main()
