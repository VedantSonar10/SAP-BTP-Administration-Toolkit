"""
api/users.py

XSUAA exposes a SCIM-compatible Users API directly on the UAA tenant
(rather than through the Accounts Service), so this client talks to
`uaa.url` instead of `endpoints.*`.
"""

from __future__ import annotations

from api.base import APIResult, BaseServiceClient


class UsersAPI(BaseServiceClient):
    """Client for the XSUAA SCIM Users endpoint."""

    service_name = "Users API"

    def test_connection(self) -> APIResult:
        """Attempt to list users via the XSUAA SCIM endpoint."""
        uaa_url = self.service_key.get("uaa", {}).get("url")
        if not uaa_url:
            return APIResult(
                service_name=self.service_name,
                url="",
                error_message="uaa.url not present in service key.",
            )
        url = f"{uaa_url}/Users?count=1"
        return self._get(url)
