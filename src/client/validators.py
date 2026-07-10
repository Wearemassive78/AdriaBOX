"""Validation helpers used by client commands and core logic."""
import os
from urllib.parse import urlparse

from client.exceptions import ClientValidationError


def require_text(value: str, field_name: str) -> str:
    """Return a stripped string or raise if it is empty."""
    if value is None:
        raise ClientValidationError(f"{field_name} is required")

    value = str(value).strip()
    if not value:
        raise ClientValidationError(f"{field_name} is required")
    return value


def require_metadata_url(value: str) -> str:
    """Validate the metadata server base URL."""
    value = require_text(value, "metadata_url").rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ClientValidationError("metadata_url must be an http(s) URL")
    return value


def require_existing_file(path: str) -> str:
    """Validate that a local file exists and is readable."""
    path = require_text(path, "filepath")
    if not os.path.isfile(path):
        raise ClientValidationError(f"file does not exist: {path}")
    return path
