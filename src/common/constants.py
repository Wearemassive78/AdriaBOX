"""Shared constants used across components."""

CHUNK_SIZE = 4096   # 4KB for TCP streaming buffer
LOGICAL_BLOCK_SIZE = 64 * 1024 * 1024   # 64MB for logical file fragmentation

DEFAULT_METADATA_URL = 'http://localhost:5000'
DEFAULT_NODE_HOST = 'localhost'
DEFAULT_NODE_TCP_PORT = 7001
METADATA_FILE = 'metadata.json'

