"""
services/access_auditor.py

User/Role Auditing via the XSUAA Authorization Management API.

IMPORTANT: this API lives on `uaa.apiurl` (NOT the same host as
`uaa.url`, and NOT any of the `endpoints.*` URLs used elsewhere in this
project). It also requires your XSUAA service instance to have been
created with the `apiaccess` plan — the default `application` plan
service key used for login will typically get a 403 here. In a real
project you'd provision a second service key:

    cf create-service xsuaa apiaccess xsuaa-api-access
    cf create-service-key xsuaa-api-access api-key

and load that second key's token specifically for this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from api.base import APIResult, BaseServiceClient

console = Console()


@dataclass
class RoleCollectionSummary:
    """Parsed view of a single role collection entry."""

    name: str
    description: str | None
    user_count: int | None


class AccessAuditor(BaseServiceClient):
    """Client for the XSUAA Authorization Management API — lists roles
    and role collections so you can audit who has access to what."""

    service_name = "Authorization Management API"

    def _api_base_url(self) -> str | None:
        return self.service_key.get("uaa", {}).get("apiurl")

    def list_roles(self) -> APIResult:
        """GET /sap/rest/authorization/v2/roles"""
        base_url = self._api_base_url()
        if not base_url:
            return APIResult(service_name=self.service_name, url="", error_message="uaa.apiurl not present in service key.")
        return self._get(f"{base_url}/sap/rest/authorization/v2/roles")

    def list_role_collections(self) -> APIResult:
        """GET /sap/rest/authorization/v2/rolecollections?showUserAndGroupCount=true"""
        base_url = self._api_base_url()
        if not base_url:
            return APIResult(service_name=self.service_name, url="", error_message="uaa.apiurl not present in service key.")
        return self._get(f"{base_url}/sap/rest/authorization/v2/rolecollections?showUserAndGroupCount=true")

    def parse_role_collections(self, result: APIResult) -> list[RoleCollectionSummary]:
        if not result.reachable or result.forbidden or result.unauthorized:
            return []

        import json

        try:
            body = json.loads(result.body_preview) if result.body_preview else []
        except json.JSONDecodeError:
            return []

        collections = body if isinstance(body, list) else body.get("rolecollections", [])
        return [
            RoleCollectionSummary(
                name=rc.get("name", "unnamed"),
                description=rc.get("description"),
                user_count=rc.get("userCount"),
            )
            for rc in collections
        ]

    def audit(self) -> APIResult:
        """Run both checks, print a combined report, and return the
        roles APIResult so callers (e.g. the dashboard) don't need to
        make a second network call just to read the status."""
        roles_result = self.list_roles()
        collections_result = self.list_role_collections()

        for label, result in (("Roles", roles_result), ("Role Collections", collections_result)):
            console.print(
                f"\n[bold cyan]{label}[/bold cyan]: {result.status_label} "
                f"(HTTP {result.status_code}, {result.latency_ms}ms)"
            )
            if result.forbidden or result.unauthorized:
                console.print(
                    "  [yellow]Access denied — this token's XSUAA instance likely isn't on "
                    "the 'apiaccess' plan.[/yellow]"
                )
            elif result.error_message:
                console.print(f"  [dim]{result.error_message}[/dim]")

        collections = self.parse_role_collections(collections_result)
        if collections:
            table = Table(title="Role Collections", header_style="bold cyan")
            table.add_column("Name")
            table.add_column("Description")
            table.add_column("Users", justify="right")
            for rc in collections:
                table.add_row(rc.name, rc.description or "N/A", str(rc.user_count) if rc.user_count is not None else "N/A")
            console.print(table)

        return roles_result
