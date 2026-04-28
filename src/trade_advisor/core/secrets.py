"""Secure key storage via keyring with .env fallback.

Priority: keyring (primary) → .env file (fallback).
On macOS the backend is explicitly pinned to the native Keychain to prevent
auto-detection from falling back to plaintext backends.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from pydantic import BaseModel, SecretStr

log = logging.getLogger("trade_advisor.secrets")

KEYRING_SERVICE = "trade_advisor"

_ALIASES: dict[str, str] = {
    "yahoo_finance": "YAHOO_API_KEY",
    "alpha_vantage": "ALPHA_VANTAGE_API_KEY",
    "polygon": "POLYGON_API_KEY",
    "twelvedata": "TWELVEDATA_API_KEY",
}

SECRET_KEY_NAMES = (
    "YAHOO_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "POLYGON_API_KEY",
    "TWELVEDATA_API_KEY",
)

_env_to_field: dict[str, str] = {
    "YAHOO_API_KEY": "yahoo_api_key",
    "ALPHA_VANTAGE_API_KEY": "alpha_vantage_api_key",
    "POLYGON_API_KEY": "polygon_api_key",
    "TWELVEDATA_API_KEY": "twelvedata_api_key",
}


def _init_keyring() -> Any:
    """Pin macOS Keychain backend on Darwin; return the keyring module."""
    import keyring

    if sys.platform == "darwin":
        try:
            from keyring.backends.macOS import Keyring as MacOSKeyring

            keyring.set_keyring(MacOSKeyring())
        except Exception:
            log.warning("Failed to pin macOS Keychain backend; using default keyring")
    return keyring


def _read_secret(kr: Any, key_name: str) -> str | None:
    try:
        val: str | None = kr.get_password(KEYRING_SERVICE, key_name)
        return val
    except Exception as exc:
        log.warning("Keyring unavailable for %s: %s", key_name, exc)
        return None


def load_secrets(env_vars: dict[str, str | None] | None = None) -> SecretsConfig:
    """Load secrets from keyring with .env/env-var fallback.

    Parameters
    ----------
    env_vars:
        Optional mapping of env var name → value (used for testing / .env source).
        If ``None``, reads from ``os.environ``.
    """
    import os

    kr = _init_keyring()
    sources: dict[str, str] = {}
    result: dict[str, str | None] = {}

    for env_name, field_name in _env_to_field.items():
        keyring_val = _read_secret(kr, env_name)
        env_val = (env_vars if env_vars is not None else os.environ).get(env_name)

        if keyring_val is not None and keyring_val.strip():
            result[field_name] = keyring_val
            sources[field_name] = "keyring"
        elif env_val is not None and env_val.strip():
            result[field_name] = env_val
            sources[field_name] = "env_fallback"
            log.warning("Keyring unavailable for %s, using .env fallback", env_name)
        else:
            result[field_name] = None

    return SecretsConfig(
        yahoo_api_key=result.get("yahoo_api_key"),
        alpha_vantage_api_key=result.get("alpha_vantage_api_key"),
        polygon_api_key=result.get("polygon_api_key"),
        twelvedata_api_key=result.get("twelvedata_api_key"),
        _secrets_source=sources,
    )


class SecretsConfig(BaseModel):
    yahoo_api_key: SecretStr | None = None
    alpha_vantage_api_key: SecretStr | None = None
    polygon_api_key: SecretStr | None = None
    twelvedata_api_key: SecretStr | None = None
    _secrets_source: dict[str, str] = {}

    def __init__(self, **data: Any) -> None:
        sources = data.pop("_secrets_source", {})
        super().__init__(**data)
        object.__setattr__(self, "_secrets_source", dict(sources))

    def get_secret_value(self, field_name: str) -> str | None:
        if field_name not in SecretsConfig.model_fields:
            raise ValueError(
                f"Unknown secret field: {field_name}. Valid: {sorted(SecretsConfig.model_fields)}"
            )
        val: SecretStr | None = getattr(self, field_name)
        if val is None:
            return None
        return val.get_secret_value()

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        d = super().model_dump(**kwargs)
        d["_secrets_source"] = dict(self._secrets_source)
        return d


def set_key(key_name: str, value: str) -> None:
    """Store a secret in keyring."""
    if not value or not value.strip():
        raise ValueError(f"Refusing to store empty secret for {key_name}")
    if key_name not in _env_to_field:
        raise ValueError(f"Unknown key: {key_name}. Valid keys: {sorted(_env_to_field)}")
    kr = _init_keyring()
    kr.set_password(KEYRING_SERVICE, key_name, value)


def get_api_key(provider: str) -> str | None:
    """Retrieve an API key for a given provider (e.g. 'yahoo_finance').

    Checks keyring first, then environment variables.
    """
    env_name = _ALIASES.get(provider, provider.upper() + "_API_KEY")
    kr = _init_keyring()
    keyring_val = _read_secret(kr, env_name)
    if keyring_val is not None and keyring_val.strip():
        return keyring_val
    import os

    env_val = os.environ.get(env_name)
    if env_val is not None and env_val.strip():
        return env_val
    return None
