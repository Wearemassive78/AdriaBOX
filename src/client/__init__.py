
"""Client package initialization.

Provides package-level metadata and an explicit export list for convenience.
"""

__all__ = [
    "api",
    "cli",
    "config",
    "core",
    "exceptions",
    "interactive",
    "session",
    "validators",
]

__version__ = "0.1.0"

from client.core import AdriaClient
