"""Configuration helpers for environment-based settings."""
import os
from .constants import DEFAULT_METADATA_URL, DEFAULT_NODE_HOST, DEFAULT_NODE_TCP_PORT, CHUNK_SIZE

def get_config():
    """Return a dict with runtime configuration read from environment with sensible defaults."""
    return {
        'metadata_url': os.environ.get('ADRIABOX_METADATA_URL', DEFAULT_METADATA_URL),
        'node_host': os.environ.get('ADRIABOX_NODE_HOST', DEFAULT_NODE_HOST),
        'node_tcp_port': int(os.environ.get('ADRIABOX_NODE_TCP_PORT', DEFAULT_NODE_TCP_PORT)),
        'chunk_size': int(os.environ.get('ADRIABOX_CHUNK_SIZE', CHUNK_SIZE)),
    }
