"""Backward-compatible import path for the AdriaBOX client.

Older tests and examples import ``AdriaClient`` from ``client.client``.
The implementation lives in ``client.core``.
"""
import requests

from client.core import AdriaClient

__all__ = ["AdriaClient", "requests"]
