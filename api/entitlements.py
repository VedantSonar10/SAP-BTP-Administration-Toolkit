"""
api/entitlements.py

Entitlements Service client — reports what service plans/quotas are
assigned to the global account/subaccount.
"""

from __future__ import annotations

from api.base import APIResult, BaseServiceClient


class EntitlementsAPI(BaseServiceClient):
    """Client for the Entitlements Service."""

    service_name = "Entitlements API"

    def test_connection(self) -> APIResult:
        """Attempt to reach the entitlements service assignments endpoint."""
        base_url = self.service_key.get("endpoints", {}).get("entitlements_service_url")
        if not base_url:
            return APIResult(
                service_name=self.service_name,
                url="",
                error_message="entitlements_service_url not present in service key.",
            )
        url = f"{base_url}/entitlements/v1/assignments"
        return self._get(url)
