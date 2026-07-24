"""
services/security_auditor.py

Security scanning via the Audit Log Retrieval API.

IMPORTANT: this requires its OWN service instance and service key —
`auditlog-management` (or the `auditlog-api` plan depending on your
landscape) — provisioned separately from the cis-central key used
elsewhere in this project:

    cf create-service auditlog-management standard auditlog-instance
    cf create-service-key auditlog-instance auditlog-key

That key's own `url` and `uaa` block are what this class expects —
pass a SEPARATE Auth instance pointed at that key's file, not the main
one used for Accounts/Entitlements.

Enterprise note: the default plan has a short retention window,
premium plans (paid) extend retention and add fields — don't promise a
manager "full audit history" without checking which plan is bound.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.table import Table

from api.base import APIResult, BaseServiceClient

console = Console()


@dataclass
class AuditLogEntry:
    """Parsed view of a single audit log record."""

    category: str
    message: str
    time: str
    user: str | None


class SecurityAuditor(BaseServiceClient):
    """Client for the Audit Log Retrieval API — surfaces security-
    relevant events like failed logins, role assignment changes, and
    configuration changes."""

    service_name = "Audit Log API"

    def _base_url(self) -> str | None:
        # The audit log service key's root `url`, not `uaa.url` and not
        # anything under `endpoints`.
        return self.service_key.get("url")

    def fetch_recent(self, hours: int = 24) -> APIResult:
        """GET /auditlog/v2/auditlogrecords for the last `hours` hours."""
        base_url = self._base_url()
        if not base_url:
            return APIResult(
                service_name=self.service_name,
                url="",
                error_message="This client needs the audit log service's own service key (its root 'url' field), not the cis-central key.",
            )

        time_to = datetime.now(timezone.utc)
        time_from = time_to - timedelta(hours=hours)
        time_from_str = time_from.strftime("%Y-%m-%dT%H:%M:%S")

        url = f"{base_url}/auditlog/v2/auditlogrecords?time_from={time_from_str}"
        return self._get(url)

    def parse_entries(self, result: APIResult) -> list[AuditLogEntry]:
        if not result.reachable or result.forbidden or result.unauthorized:
            return []
        try:
            body = json.loads(result.body_preview) if result.body_preview else []
        except json.JSONDecodeError:
            return []

        records = body if isinstance(body, list) else body.get("records", [])
        return [
            AuditLogEntry(
                category=r.get("category", "unknown"),
                message=r.get("message", ""),
                time=r.get("time", ""),
                user=r.get("user"),
            )
            for r in records
        ]

    def scan(self, hours: int = 24) -> APIResult:
        """Fetch and display recent audit events. Returns the APIResult
        so callers (e.g. the dashboard) don't need a second network
        call just to read the status."""
        result = self.fetch_recent(hours=hours)

        console.print(
            f"\n[bold cyan]Audit Log API[/bold cyan]: {result.status_label} "
            f"(HTTP {result.status_code}, {result.latency_ms}ms)"
        )
        if result.error_message:
            console.print(f"  [dim]{result.error_message}[/dim]")
            return result
        if result.forbidden or result.unauthorized:
            console.print("  [yellow]Access denied — check the audit log service key's scopes.[/yellow]")
            return result

        entries = self.parse_entries(result)
        if not entries:
            console.print(f"  [dim]No audit events in the last {hours}h (or none returned).[/dim]")
            return result

        table = Table(title=f"Audit Log — last {hours}h", header_style="bold cyan")
        table.add_column("Time")
        table.add_column("Category")
        table.add_column("User")
        table.add_column("Message", overflow="fold")
        for e in entries[:25]:  # cap display, full data is still in the raw response
            table.add_row(e.time, e.category, e.user or "N/A", e.message)
        console.print(table)

        return result
