import os
import socket

from .constants import CHUNK_SIZE

def send_file(host, port, filename):
    """Send a file to a storage node over a simple TCP protocol.

    First packet: filename (with newline). Remaining bytes: file contents.
    """
    s = socket.socket()
    s.connect((host, port))
    # send filename as first packet
    s.sendall((os.path.basename(filename) + '\n').encode('utf-8'))
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            s.sendall(chunk)
    s.close()

def handle_connection(conn, storage_dir):
    """Handle an incoming connection: read header filename then stream to disk."""
    try:
        with conn:
            header = conn.recv(1024)
            if not header:
                return
            filename = header.decode('utf-8').strip()
            out_path = os.path.join(storage_dir, filename)
            with open(out_path, 'wb') as f:
                while True:
                    chunk = conn.recv(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
    except Exception:
        pass
