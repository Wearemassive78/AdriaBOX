"""Client-side exception types."""


class AdriaClientError(Exception):
    """Base exception for client failures."""


class ClientValidationError(AdriaClientError, ValueError):
    """Raised when user input is missing or malformed."""


class AuthenticationError(AdriaClientError):
    """Raised when an authenticated action has no active token."""
