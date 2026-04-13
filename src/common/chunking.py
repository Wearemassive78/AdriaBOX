"""Helpers for reading and writing file chunks."""
from .constants import CHUNK_SIZE

def iter_file_chunks(path, size=CHUNK_SIZE):
    """Yield successive chunks (bytes) from file at `path` using `size`."""
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(size)
            if not chunk:
                break
            yield chunk

def write_chunks(dest_path, chunks):
    """Write an iterable of bytes `chunks` to `dest_path`."""
    with open(dest_path, 'wb') as f:
        for c in chunks:
            f.write(c)
