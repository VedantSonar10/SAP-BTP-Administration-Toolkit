"""
utils/config.py

Phase 8 - Configuration

Loads runtime settings from a .env file instead of hardcoding them.
Everything else in the toolkit (auth, endpoint checker, logger) should
pull its settings from an AppConfig instance rather than reading
os.environ directly, so there's one place that knows the defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from utils.exceptions import ConfigurationError

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass
class AppConfig:
    """Resolved, validated configuration for a single run of the toolkit."""

    service_key_path: str
    log_level: str
    timeout: int
    audit_log_service_key_path: str | None
    apiaccess_service_key_path: str | None

    @classmethod
    def load(cls, dotenv_path: str | None = None) -> "AppConfig":
        """Load configuration from environment variables / a .env file.

        Raises:
            ConfigurationError: if a required value is missing or a
                value fails validation (e.g. TIMEOUT isn't an integer).
        """
        load_dotenv(dotenv_path=dotenv_path)

        service_key_path = os.getenv("SERVICE_KEY_PATH", "config/service_key.json")
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        timeout_raw = os.getenv("TIMEOUT", "10")
        # Optional: only needed for the Security Auditor (Audit Log API),
        # which uses a separate service instance/key from the main one.
        # Absence here should never block startup of the rest of the toolkit.
        audit_log_service_key_path = os.getenv("AUDIT_LOG_SERVICE_KEY_PATH")
        # Optional: only needed for the Access Auditor (Authorization
        # Management API), which requires an XSUAA instance on the
        # 'apiaccess' plan — a separate key from the main login one.
        apiaccess_service_key_path = os.getenv("APIACCESS_SERVICE_KEY_PATH")

        if log_level not in VALID_LOG_LEVELS:
            raise ConfigurationError(
                f"LOG_LEVEL '{log_level}' is invalid. Must be one of {sorted(VALID_LOG_LEVELS)}."
            )

        try:
            timeout = int(timeout_raw)
        except ValueError as exc:
            raise ConfigurationError(f"TIMEOUT must be an integer, got '{timeout_raw}'.") from exc

        if timeout <= 0:
            raise ConfigurationError("TIMEOUT must be a positive integer.")

        if not Path(service_key_path).exists():
            raise ConfigurationError(
                f"Service key not found at '{service_key_path}'. "
                "Set SERVICE_KEY_PATH in .env or copy config/service_key.example.json "
                "to config/service_key.json with your real credentials."
            )

        return cls(
            service_key_path=service_key_path,
            log_level=log_level,
            timeout=timeout,
            audit_log_service_key_path=audit_log_service_key_path,
            apiaccess_service_key_path=apiaccess_service_key_path,
        )
