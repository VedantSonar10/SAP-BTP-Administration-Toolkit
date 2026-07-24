"""
services/cost_tracker.py

Cost Tracking via the SAP Cloud Management Service's Account Budgets API.

Reads spend/quota limits configured against the global account or
subaccount. Note: on a BTP Trial landscape this will very likely
return 403/404 the same way the Accounts API does — trial accounts
aren't entitled to budget management. That's expected, not a bug.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from api.base import APIResult, BaseServiceClient

console = Console()


@dataclass
class BudgetSummary:
    """Parsed view of a single budget entry, when the API is reachable
    and returns data (requires an entitled landscape, not trial)."""

    name: str
    amount: float | None
    currency: str | None
    period: str | None


class CostTracker(BaseServiceClient):
    """Client for the Account Budgets Service."""

    service_name = "Account Budgets API"

    def test_connection(self) -> APIResult:
        """Attempt to reach the budgets listing endpoint."""
        base_url = self.service_key.get("endpoints", {}).get("account_budgets_service_url")
        if not base_url:
            return APIResult(
                service_name=self.service_name,
                url="",
                error_message="account_budgets_service_url not present in service key.",
            )
        url = f"{base_url}/budgets/v1/budgets"
        return self._get(url)

    def parse_budgets(self, result: APIResult) -> list[BudgetSummary]:
        """Best-effort parse of a successful budgets response into
        BudgetSummary objects. Returns an empty list if the response
        wasn't a usable JSON body (e.g. a 403 error page)."""
        if not result.reachable or result.forbidden or result.unauthorized:
            return []

        import json

        try:
            body = json.loads(result.body_preview) if result.body_preview else {}
        except json.JSONDecodeError:
            return []

        budgets = body.get("budgets", []) if isinstance(body, dict) else []
        return [
            BudgetSummary(
                name=b.get("name", "unnamed"),
                amount=b.get("amount"),
                currency=b.get("currency"),
                period=b.get("period"),
            )
            for b in budgets
        ]

    def display(self, result: APIResult) -> None:
        console.print(
            f"\n[bold cyan]Account Budgets API[/bold cyan]: {result.status_label} "
            f"(HTTP {result.status_code}, {result.latency_ms}ms)"
        )
        if result.error_message:
            console.print(f"  [dim]{result.error_message}[/dim]")
            return

        if result.forbidden or result.unauthorized:
            console.print(
                "  [yellow]Access denied — this landscape/plan is not entitled to "
                "budget management. Common on BTP Trial.[/yellow]"
            )
            return

        budgets = self.parse_budgets(result)
        if not budgets:
            console.print("  [dim]No budget data returned.[/dim]")
            return

        table = Table(title="Budgets", header_style="bold cyan")
        table.add_column("Name")
        table.add_column("Amount", justify="right")
        table.add_column("Currency")
        table.add_column("Period")
        for b in budgets:
            table.add_row(b.name, str(b.amount), b.currency or "N/A", b.period or "N/A")
        console.print(table)
