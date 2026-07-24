"""
api/accounts.py

Accounts Service client. On a BTP trial landscape this reliably returns
403 insufficient_scope — that's expected and handled, not treated as a
crash.
"""

from __future__ import annotations

from api.base import APIResult, BaseServiceClient


class AccountsAPI(BaseServiceClient):
    """Client for the Accounts Service (global account / directory
    metadata)."""

    service_name = "Accounts API"

    def test_connection(self) -> APIResult:
        """Attempt to reach the accounts service `/accounts/v1/labels`
        endpoint and return a classified APIResult."""
        base_url = self.service_key.get("endpoints", {}).get("accounts_service_url")
        if not base_url:
            return APIResult(
                service_name=self.service_name,
                url="",
                error_message="accounts_service_url not present in service key.",
            )
        url = f"{base_url}/accounts/v1/labels"
        return self._get(url)
