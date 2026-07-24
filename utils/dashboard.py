"""
utils/dashboard.py

Phase 4 - Professional Dashboard

Renders a status overview of the current session. Called after every
menu action so the picture is always current, rather than being a
static "coming soon" panel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class DashboardState:
    """Everything the dashboard needs to know about the current
    session. app.py owns the single instance of this and updates it
    after each action."""

    authenticated: bool = False
    identity_zone: str | None = None
    token_valid: bool = False
    accounts_status: str = "Not Tested"
    entitlements_status: str = "Not Tested"
    users_status: str = "Not Tested"
    provisioning_status: str = "Not Tested"
    metadata_status: str = "Not Tested"
    events_status: str = "Not Tested"
    budgets_status: str = "Not Tested"
    access_audit_status: str = "Not Tested"
    security_audit_status: str = "Not Tested"


_STATUS_ICON = {
    "Reachable": "[green]✅ Reachable[/green]",
    "Forbidden": "[yellow]🚫 Forbidden[/yellow]",
    "Unauthorized": "[yellow]🔒 Unauthorized[/yellow]",
    "Timeout": "[red]⏱ Timeout[/red]",
    "Network Error": "[red]❌ Network Error[/red]",
    "Not Tested": "[dim]— Not Tested[/dim]",
}


def _icon(status: str) -> str:
    return _STATUS_ICON.get(status, status)


def show_dashboard(state: DashboardState) -> None:
    """Render the current session state as a Rich panel + table."""

    header = Table.grid(padding=(0, 2))
    header.add_column(style="cyan", justify="right")
    header.add_column(style="white")

    header.add_row("Authentication", "[green]✅ Authenticated[/green]" if state.authenticated else "[red]❌ Not Authenticated[/red]")
    header.add_row("JWT Status", "[green]✅ Valid[/green]" if state.token_valid else "[dim]— No Token[/dim]")
    header.add_row("Identity Zone", state.identity_zone or "N/A")

    api_table = Table(title="API Health", header_style="bold cyan")
    api_table.add_column("Service")
    api_table.add_column("Status")

    api_table.add_row("Accounts API", _icon(state.accounts_status))
    api_table.add_row("Entitlements API", _icon(state.entitlements_status))
    api_table.add_row("Users API", _icon(state.users_status))
    api_table.add_row("Provisioning API", _icon(state.provisioning_status))
    api_table.add_row("Metadata API", _icon(state.metadata_status))
    api_table.add_row("Events API", _icon(state.events_status))
    api_table.add_row("Account Budgets (Cost)", _icon(state.budgets_status))
    api_table.add_row("Access Audit (Roles)", _icon(state.access_audit_status))
    api_table.add_row("Security Audit (Audit Log)", _icon(state.security_audit_status))

    console.print(Panel(header, title="SAP BTP Administration Toolkit", border_style="blue"))
    console.print(api_table)
