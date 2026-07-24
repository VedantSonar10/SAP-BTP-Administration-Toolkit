"""
services/endpoint_checker.py

Phase 5 - Endpoint Health Checker

Reads every endpoint listed in the service key and attempts a live GET
against each, reporting reachability, latency, and HTTP status with
colour coding.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from rich.console import Console
from rich.table import Table

from utils.logger import logger

console = Console()

_STATUS_STYLE = {
    "Reachable": "green",
    "Forbidden": "yellow",
    "Unauthorized": "yellow",
    "Timeout": "red",
    "Network Error": "red",
    "Unknown": "dim",
}


@dataclass
class EndpointCheckResult:
    """Outcome of pinging one endpoint from the service key."""

    name: str
    url: str
    status_label: str
    status_code: int | None
    latency_ms: float | None


class EndpointChecker:
    """Sweeps every endpoint in a service key with a bare GET request
    (no auth) purely to check reachability and latency — this is a
    network health check, not an authenticated API test."""

    def __init__(self, service_key: dict, timeout: int = 10) -> None:
        self.service_key = service_key
        self.timeout = timeout

    def check_all(self) -> list[EndpointCheckResult]:
        endpoints = self.service_key.get("endpoints", {})
        results: list[EndpointCheckResult] = []

        for name, url in endpoints.items():
            results.append(self._check_one(name, url))

        return results

    def _check_one(self, name: str, url: str) -> EndpointCheckResult:
        start = time.monotonic()
        try:
            response = requests.get(url, timeout=self.timeout)
        except requests.exceptions.Timeout:
            logger.warning("Endpoint check timed out: %s (%s)", name, url)
            return EndpointCheckResult(name, url, "Timeout", None, None)
        except requests.exceptions.RequestException as exc:
            logger.warning("Endpoint check network error: %s (%s): %s", name, url, exc)
            return EndpointCheckResult(name, url, "Network Error", None, None)

        latency_ms = round((time.monotonic() - start) * 1000, 1)

        if response.status_code == 403:
            label = "Forbidden"
        elif response.status_code == 401:
            label = "Unauthorized"
        elif response.status_code < 500:
            label = "Reachable"
        else:
            label = "Reachable"

        logger.info("Endpoint check: %s -> %s (%sms)", name, label, latency_ms)
        return EndpointCheckResult(name, url, label, response.status_code, latency_ms)

    def display(self, results: list[EndpointCheckResult]) -> None:
        table = Table(title="Endpoint Health Check", header_style="bold cyan")
        table.add_column("Endpoint")
        table.add_column("Status")
        table.add_column("HTTP Code", justify="right")
        table.add_column("Latency (ms)", justify="right")

        for r in results:
            style = _STATUS_STYLE.get(r.status_label, "white")
            table.add_row(
                r.name,
                f"[{style}]{r.status_label}[/{style}]",
                str(r.status_code) if r.status_code is not None else "-",
                f"{r.latency_ms}" if r.latency_ms is not None else "-",
            )

        console.print(table)
