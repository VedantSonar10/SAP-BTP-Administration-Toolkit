"""
utils/exceptions.py

Central exception hierarchy for the toolkit. Every layer (api/, services/)
raises one of these instead of letting requests/json/jwt exceptions bubble
up raw — app.py only ever needs to catch BTPToolkitError.
"""


class BTPToolkitError(Exception):
    """Base class for every error this toolkit raises intentionally."""


class ConfigurationError(BTPToolkitError):
    """Raised when required configuration (.env, service key path) is
    missing or invalid."""


class ServiceKeyError(BTPToolkitError):
    """Raised when the service key file is missing, unreadable, or
    malformed."""


class AuthenticationError(BTPToolkitError):
    """Raised when the OAuth client-credentials flow fails."""


class TokenDecodeError(BTPToolkitError):
    """Raised when a JWT cannot be parsed."""


class APIConnectionError(BTPToolkitError):
    """Raised when a request to a BTP service endpoint fails at the
    network level (timeout, DNS, connection refused)."""
