"""
services/quota_checker.py

Quota Alert — the thing a BTP admin does manually in the cockpit
(Entitlements > check usage > notice something's close to its limit),
automated.

Honesty note: the Entitlements assignments response schema varies by
service. Some plans report both an entitled `amount` and a consumed
amount (fields vary: `usedAmount`, `consumedAmount`, `remainingAmount`
depending on the service). Where consumption data isn't present in
the response, this checker says so explicitly rather than inventing a
percentage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from api.base import APIResult

console = Console()

WARNING_THRESHOLD_PCT = 80.0


@dataclass
class QuotaStatus:
    """Parsed usage status for a single entitlement assignment."""

    service: str
    plan: str
    entitled_amount: float | None
    used_amount: float | None

    @property
    def usage_pct(self) -> float | None:
        if self.entitled_amount in (None, 0) or self.used_amount is None:
            return None
        return round((self.used_amount / self.entitled_amount) * 100, 1)

    @property
    def is_over_threshold(self) -> bool:
        pct = self.usage_pct
        return pct is not None and pct >= WARNING_THRESHOLD_PCT

    @property
    def has_usage_data(self) -> bool:
        return self.entitled_amount is not None and self.used_amount is not None


class QuotaChecker:
    """Parses an Entitlements API response and flags anything at or
    above the warning threshold."""

    def __init__(self, threshold_pct: float = WARNING_THRESHOLD_PCT) -> None:
        self.threshold_pct = threshold_pct

    def parse(self, result: APIResult) -> list[QuotaStatus]:
        """Best-effort parse of the assignments body. Returns an empty
        list if the response wasn't reachable/authorized, or wasn't
        JSON we recognize."""
        if not result.reachable or result.forbidden or result.unauthorized:
            return []

        try:
            body = json.loads(result.body_preview) if result.body_preview else {}
        except json.JSONDecodeError:
            return []

        assignments = body.get("assignments", []) if isinstance(body, dict) else body
        if not isinstance(assignments, list):
            return []

        statuses = []
        for a in assignments:
            statuses.append(
                QuotaStatus(
                    service=a.get("entityName", a.get("service", "unknown")),
                    plan=a.get("planName", a.get("plan", "unknown")),
                    entitled_amount=a.get("amount"),
                    used_amount=a.get("usedAmount") or a.get("consumedAmount"),
                )
            )
        return statuses

    def check(self, result: APIResult) -> list[QuotaStatus]:
        """Parse, display a table, and print warnings for anything over
        threshold. Returns the parsed statuses for reuse (e.g. reports)."""
        console.print(
            f"\n[bold cyan]Entitlements API[/bold cyan]: {result.status_label} "
            f"(HTTP {result.status_code}, {result.latency_ms}ms)"
        )

        if result.forbidden or result.unauthorized:
            console.print(
                "  [yellow]Access denied — cannot read entitlement assignments on this landscape/plan.[/yellow]"
            )
            return []
        if result.error_message:
            console.print(f"  [dim]{result.error_message}[/dim]")
            return []

        statuses = self.parse(result)
        if not statuses:
            console.print("  [dim]No entitlement assignments returned.[/dim]")
            return []

        table = Table(title="Entitlement Quota Status", header_style="bold cyan")
        table.add_column("Service")
        table.add_column("Plan")
        table.add_column("Entitled", justify="right")
        table.add_column("Used", justify="right")
        table.add_column("Usage %", justify="right")

        any_alert = False
        for s in statuses:
            if not s.has_usage_data:
                table.add_row(s.service, s.plan, str(s.entitled_amount or "N/A"), "N/A", "[dim]no usage data[/dim]")
                continue

            pct = s.usage_pct
            style = "red" if s.is_over_threshold else "green"
            table.add_row(
                s.service, s.plan, str(s.entitled_amount), str(s.used_amount),
                f"[{style}]{pct}%[/{style}]",
            )
            if s.is_over_threshold:
                any_alert = True

        console.print(table)

        for s in statuses:
            if s.is_over_threshold:
                console.print(
                    f"  [bold red]⚠ WARNING:[/bold red] {s.service} ({s.plan}) is at "
                    f"{s.usage_pct}% of its entitled quota (threshold: {self.threshold_pct}%)"
                )

        if not any_alert and any(s.has_usage_data for s in statuses):
            console.print("  [green]All entitlements within threshold.[/green]")

        return statuses
