"""
api/base.py

Shared plumbing for the individual BTP service clients (accounts,
entitlements, users) so each one isn't reimplementing the same
GET-and-classify logic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests

from utils.logger import logger


@dataclass
class APIResult:
    """Outcome of a single call against a BTP service endpoint."""

    service_name: str
    url: str
    reachable: bool = False
    forbidden: bool = False
    unauthorized: bool = False
    timed_out: bool = False
    network_error: bool = False
    status_code: int | None = None
    latency_ms: float | None = None
    error_message: str | None = None
    body_preview: str = ""
    headers: dict[str, Any] = field(default_factory=dict)

    @property
    def status_label(self) -> str:
        if self.timed_out:
            return "Timeout"
        if self.network_error:
            return "Network Error"
        if self.forbidden:
            return "Forbidden"
        if self.unauthorized:
            return "Unauthorized"
        if self.reachable:
            return "Reachable"
        return "Unknown"


class BaseServiceClient:
    """Common request/classify logic for a single BTP service."""

    #: Overridden by subclasses to name the service in logs/reports.
    service_name: str = "generic"

    def __init__(self, service_key: dict, access_token: str, timeout: int = 10) -> None:
        self.service_key = service_key
        self.access_token = access_token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def _get(self, url: str) -> APIResult:
        """Perform a GET against `url` and classify the outcome. Never
        raises — network/timeout/HTTP errors are all captured in the
        returned APIResult so the CLI can display them uniformly."""
        result = APIResult(service_name=self.service_name, url=url)
        start = time.monotonic()

        try:
            response = requests.get(url, headers=self._headers(), timeout=self.timeout)
        except requests.exceptions.Timeout:
            result.timed_out = True
            result.error_message = f"Request to {self.service_name} timed out after {self.timeout}s."
            logger.warning(result.error_message)
            return result
        except requests.exceptions.RequestException as exc:
            result.network_error = True
            result.error_message = f"Network error contacting {self.service_name}: {exc}"
            logger.warning(result.error_message)
            return result

        result.latency_ms = round((time.monotonic() - start) * 1000, 1)
        result.status_code = response.status_code
        result.headers = dict(response.headers)
        result.body_preview = (response.text or "")[:300]

        if response.status_code == 200:
            result.reachable = True
        elif response.status_code == 403:
            result.forbidden = True
            result.reachable = True
        elif response.status_code == 401:
            result.unauthorized = True
            result.reachable = True
        else:
            result.reachable = True  # host responded, just not a success code

        logger.info(
            "%s -> %s (%s, %sms)",
            self.service_name,
            url,
            result.status_label,
            result.latency_ms,
        )
        return result
