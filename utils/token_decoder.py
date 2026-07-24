"""
utils/token_decoder.py

Phase 2 - JWT Inspector

Decodes an SAP BTP / XSUAA OAuth access token and renders its key claims
in a readable, professional format using Rich. Signature verification is
intentionally skipped here (this is an inspection tool, not an auth
gate) — the token was already validated by the identity zone when it
was issued.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import jwt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class TokenInfo:
    """Structured view of the claims we care about in an XSUAA token."""

    client_id: str | None
    grant_type: str | None
    identity_zone: str | None
    global_account: str | None
    subaccount_zone: str | None
    scopes: list[str]
    authorities: list[str]
    issued_at: datetime | None
    expires_at: datetime | None

    @property
    def lifetime_seconds(self) -> int | None:
        if self.issued_at and self.expires_at:
            return int((self.expires_at - self.issued_at).total_seconds())
        return None

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at


def _as_list(value: Any) -> list[str]:
    """Normalize a claim that may arrive as a list, a space-delimited
    string, or be absent entirely."""
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return value.split()
    return [str(value)]


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def parse_token(token: str) -> TokenInfo:
    """Decode the JWT payload (no signature verification) into a
    TokenInfo. Raises jwt.DecodeError if the token is malformed."""
    payload = jwt.decode(token, options={"verify_signature": False})
    ext = payload.get("ext_attr", {}) or {}

    return TokenInfo(
        client_id=payload.get("client_id"),
        grant_type=payload.get("grant_type"),
        identity_zone=payload.get("zid"),
        global_account=ext.get("globalaccountid"),
        subaccount_zone=ext.get("zdn"),
        scopes=_as_list(payload.get("scope")),
        authorities=_as_list(payload.get("authorities")),
        issued_at=_parse_timestamp(payload.get("iat")),
        expires_at=_parse_timestamp(payload.get("exp")),
    )


def _format_lifetime(seconds: int | None) -> str:
    if seconds is None:
        return "N/A"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _render_claims_table(info: TokenInfo) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    status = "[red]EXPIRED[/red]" if info.is_expired else "[green]Valid[/green]"

    rows = [
        ("Client ID", info.client_id or "N/A"),
        ("Grant Type", info.grant_type or "N/A"),
        ("Identity Zone", info.identity_zone or "N/A"),
        ("Global Account", info.global_account or "N/A"),
        ("Subaccount Zone", info.subaccount_zone or "N/A"),
        ("Issued At", info.issued_at.strftime("%Y-%m-%d %H:%M:%S UTC") if info.issued_at else "N/A"),
        ("Expires At", info.expires_at.strftime("%Y-%m-%d %H:%M:%S UTC") if info.expires_at else "N/A"),
        ("Token Lifetime", _format_lifetime(info.lifetime_seconds)),
        ("Status", status),
    ]
    for field, value in rows:
        table.add_row(field, value)

    return table


def decode_token(token: str) -> TokenInfo | None:
    """Public entry point used by app.py. Parses the token, prints a
    formatted report, and returns the TokenInfo for reuse elsewhere
    (e.g. the dashboard in Phase 4)."""
    try:
        info = parse_token(token)
    except jwt.DecodeError:
        console.print("[bold red]Unable to decode token — it does not appear to be a valid JWT.[/bold red]")
        return None

    console.print(Panel(_render_claims_table(info), title="Access Token Information", border_style="blue"))

    if info.scopes:
        scope_table = Table(title="Scopes", show_header=False, box=None)
        scope_table.add_column(style="magenta")
        for scope in info.scopes:
            scope_table.add_row(f"• {scope}")
        console.print(scope_table)
    else:
        console.print("[dim]No scopes present on this token.[/dim]")

    if info.authorities:
        auth_table = Table(title="Authorities", show_header=False, box=None)
        auth_table.add_column(style="yellow")
        for authority in info.authorities:
            auth_table.add_row(f"• {authority}")
        console.print(auth_table)

    return info
