"""Client-specific runtime configuration."""
from dataclasses import dataclass
import os

from common.constants import DEFAULT_METADATA_URL


@dataclass(frozen=True)
class ClientConfig:
    """Settings needed by the command-line client."""

    metadata_url: str = DEFAULT_METADATA_URL
    request_timeout: float = 10.0


def load_client_config() -> ClientConfig:
    """Load client settings from environment variables."""
    return ClientConfig(
        metadata_url=os.environ.get("ADRIABOX_METADATA_URL", DEFAULT_METADATA_URL),
        request_timeout=float(os.environ.get("ADRIABOX_REQUEST_TIMEOUT", "10")),
    )
