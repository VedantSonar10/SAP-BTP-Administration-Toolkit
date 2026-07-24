"""
services/inventory_exporter.py

Governance-style "subaccount inventory" export — the kind of artifact
a BTP admin hands to a compliance/audit review: what's entitled, what's
being used, and what's reachable, in one CSV.

This is deliberately a SEPARATE file from services/report_generator.py:
report_generator.py exports a session snapshot (auth + endpoint checks);
this exports a point-in-time inventory of the subaccount itself.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from services.quota_checker import QuotaStatus
from services.service_key_analyzer import ServiceKeyInfo
from utils.logger import logger

REPORTS_DIR = Path("reports")


class InventoryExporter:
    """Writes a subaccount inventory CSV combining service key identity,
    entitlement/quota status, and endpoint reachability."""

    def __init__(self) -> None:
        REPORTS_DIR.mkdir(exist_ok=True)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def export(
        self,
        service_key_info: ServiceKeyInfo,
        quota_statuses: list[QuotaStatus],
        endpoint_results: list,
    ) -> Path:
        """Write the inventory CSV and return its path."""
        path = REPORTS_DIR / f"subaccount_inventory_{self._timestamp()}.csv"

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow(["SUBACCOUNT IDENTITY"])
            writer.writerow(["Identity Zone", service_key_info.identity_zone or "N/A"])
            writer.writerow(["Identity Zone ID", service_key_info.identity_zone_id or "N/A"])
            writer.writerow(["Region", service_key_info.region or "Unknown"])
            writer.writerow(["Service Instance ID", service_key_info.service_instance_id or "N/A"])
            writer.writerow(["Global Account", service_key_info.global_account or "Not present in service key"])
            writer.writerow([])

            writer.writerow(["ENTITLEMENTS & QUOTA"])
            writer.writerow(["Service", "Plan", "Entitled Amount", "Used Amount", "Usage %", "Alert"])
            for q in quota_statuses:
                alert = "OVER THRESHOLD" if q.is_over_threshold else ("OK" if q.has_usage_data else "NO DATA")
                writer.writerow([q.service, q.plan, q.entitled_amount, q.used_amount, q.usage_pct, alert])
            writer.writerow([])

            writer.writerow(["ENDPOINT REACHABILITY"])
            writer.writerow(["Endpoint", "Status", "HTTP Code", "Latency (ms)"])
            for r in endpoint_results:
                writer.writerow([r.name, r.status_label, r.status_code, r.latency_ms])

        logger.info("Subaccount inventory exported: %s", path.name)
        return path
