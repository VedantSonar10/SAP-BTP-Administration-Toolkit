"""
api/auth.py

Phase 1 - Authentication (unchanged in spirit, hardened in Phase 9)

Reads an SAP BTP service key and performs the OAuth 2.0 client
credentials flow against the XSUAA tenant to obtain an access token.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import requests

from utils.exceptions import AuthenticationError, ServiceKeyError
from utils.logger import logger


@dataclass
class TokenResponse:
    """Raw result of a successful token request."""

    access_token: str
    expires_in: int
    token_type: str


class Auth:
    """Handles loading the service key and exchanging it for an OAuth
    access token via the client credentials grant."""

    def __init__(self, service_key_path: str, timeout: int = 10) -> None:
        self.service_key_path = service_key_path
        self.timeout = timeout
        self.service_key: dict = self._load_service_key(service_key_path)

    @staticmethod
    def _load_service_key(path: str) -> dict:
        service_key_file = Path(path)
        if not service_key_file.exists():
            raise ServiceKeyError(f"Service key file not found: {path}")

        try:
            with service_key_file.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as exc:
            raise ServiceKeyError(f"Service key file is not valid JSON: {path}") from exc

    def get_service_key(self) -> dict:
        """Return the parsed service key dict."""
        return self.service_key

    def get_access_token(self) -> str:
        """Perform the client credentials flow and return the access token.

        Raises:
            AuthenticationError: on any non-200 response, network
                failure, or malformed service key section.
        """
        try:
            uaa = self.service_key["uaa"]
            token_url = f"{uaa['url']}/oauth/token"
            client_id = uaa["clientid"]
            client_secret = uaa["clientsecret"]
        except KeyError as exc:
            logger.error("Service key missing expected uaa field: %s", exc)
            raise AuthenticationError(
                f"Service key is missing the expected 'uaa.{exc}' field."
            ) from exc

        try:
            response = requests.post(
                token_url,
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            logger.error("Authentication timed out after %ss", self.timeout)
            raise AuthenticationError("Connection Timeout while authenticating.") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Authentication network error: %s", exc)
            raise AuthenticationError("Unable to reach SAP Authentication Server.") from exc

        if response.status_code != 200:
            logger.warning(
                "Authentication failed with status %s: %s",
                response.status_code,
                response.text[:200],
            )
            raise AuthenticationError(
                f"Authentication Failed (HTTP {response.status_code}). "
                "Check your client ID / secret in the service key."
            )

        body = response.json()
        logger.info("Authentication successful (expires in %ss)", body.get("expires_in"))

        return body["access_token"]
