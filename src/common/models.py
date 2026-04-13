"""Simple data models used across the project."""
from dataclasses import dataclass
from typing import Optional

@dataclass
class FileMeta:
    file_id: Optional[str]
    filename: str
    chunks: int = 1

@dataclass
class ChunkInfo:
    index: int
    size: int

@dataclass
class StoreResponse:
    id: int
    filename: str
