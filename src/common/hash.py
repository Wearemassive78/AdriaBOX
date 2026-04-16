"""Hashing utilities for files and chunks (SHA-256).

Provides helpers to compute file hashes, per-chunk hashes and verify expected hashes.
"""
import hashlib
from typing import Iterator, Tuple
from .constants import CHUNK_SIZE


def chunk_sha256(data: bytes) -> str:
    """Return the SHA-256 hex digest of the given bytes."""
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: str, chunk_size: int = CHUNK_SIZE) -> str:
    """Compute SHA-256 hash of a file by streaming it in chunks.

    Returns the hex digest string.
    """
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def iter_chunk_hashes(path: str, chunk_size: int = CHUNK_SIZE) -> Iterator[Tuple[int, str]]:
    """Yield (index, hex-hash) for each chunk of the file at `path`.

    Index starts at 0.
    """
    idx = 0
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield idx, hashlib.sha256(chunk).hexdigest()
            idx += 1


def verify_file_hash(path: str, expected_hex: str, chunk_size: int = CHUNK_SIZE) -> bool:
    """Return True if the computed file SHA-256 matches `expected_hex`."""
    return file_sha256(path, chunk_size) == expected_hex
