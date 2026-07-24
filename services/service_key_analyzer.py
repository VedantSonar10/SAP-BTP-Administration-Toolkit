"""
services/service_key_analyzer.py

Phase 3 - Service Key Analyzer (expanded)

Parses a BTP service key and presents its structure without ever
printing the client secret itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# SAP data-center region codes embedded in most BTP hostnames,
# e.g. https://foo.cfapps.eu10.hana.ondemand.com -> "eu10"
_REGION_PATTERN = re.compile(r"\.(?P<region>[a-z]{2}\d{1,2})\.hana\.ondemand\.com")


@dataclass
class ServiceKeyInfo:
    """Structured, secret-free view of a service key."""

    client_id: str | None
    client_secret_length: int
    identity_zone: str | None
    identity_zone_id: str | None
    auth_url: str | None
    region: str | None
    service_instance_id: str | None
    tenant_mode: str | None
    credential_type: str | None
    xsappname: str | None
    global_account: str | None
    endpoints: dict[str, str] = field(default_factory=dict)


class ServiceKeyAnalyzer:
    """Extracts and displays the shape of a service key without ever
    surfacing the client secret."""

    def __init__(self, service_key: dict) -> None:
        self.service_key = service_key

    def _detect_region(self, url: str | None) -> str | None:
        if not url:
            return None
        match = _REGION_PATTERN.search(url)
        return match.group("region") if match else None

    def parse(self) -> ServiceKeyInfo:
        uaa = self.service_key.get("uaa", {})
        secret = uaa.get("clientsecret", "")

        return ServiceKeyInfo(
            client_id=uaa.get("clientid"),
            client_secret_length=len(secret),
            identity_zone=uaa.get("identityzone"),
            identity_zone_id=uaa.get("identityzoneid"),
            auth_url=uaa.get("url"),
            region=self._detect_region(uaa.get("url")),
            service_instance_id=uaa.get("serviceInstanceId"),
            tenant_mode=uaa.get("tenantmode"),
            credential_type=uaa.get("credential-type"),
            xsappname=uaa.get("xsappname"),
            global_account=self.service_key.get("globalAccountGUID") or self.service_key.get("global_account_guid"),
            endpoints=self.service_key.get("endpoints", {}),
        )

    def analyze(self) -> ServiceKeyInfo:
        """Parse the service key and render a formatted report."""
        info = self.parse()

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        rows = [
            ("Client ID", info.client_id or "N/A"),
            ("Client Secret Length", f"{info.client_secret_length} characters (value hidden)"),
            ("Identity Zone", info.identity_zone or "N/A"),
            ("Identity Zone ID", info.identity_zone_id or "N/A"),
            ("Authentication URL", info.auth_url or "N/A"),
            ("Region", info.region or "Unknown"),
            ("Global Account", info.global_account or "Not present in service key (see decoded token)"),
            ("Service Instance ID", info.service_instance_id or "N/A"),
            ("XSUAA Tenant Mode", info.tenant_mode or "N/A"),
            ("XSUAA Credential Type", info.credential_type or "N/A"),
            ("XSUAA App Name", info.xsappname or "N/A"),
        ]
        for field_name, value in rows:
            table.add_row(field_name, value)

        console.print(Panel(table, title="Service Key Analysis", border_style="blue"))

        if info.endpoints:
            endpoint_table = Table(title="Available Endpoints", show_header=True, header_style="bold cyan")
            endpoint_table.add_column("Service")
            endpoint_table.add_column("URL", overflow="fold")
            for name, url in info.endpoints.items():
                endpoint_table.add_row(name, url)
            console.print(endpoint_table)
        else:
            console.print("[dim]No endpoints listed in this service key.[/dim]")

        return info
