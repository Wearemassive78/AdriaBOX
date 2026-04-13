"""TCP helpers for sending and receiving files with a simple newline-framed header.

Provides `send_file` for clients and `handle_connection` for storage nodes.
"""
import os
import socket
from .constants import CHUNK_SIZE


def send_file(host, port, filename):
    """Send a file to a storage node.

    Protocol: first packet is the basename followed by a newline, remaining
    data is the file bytes.
    """
    s = socket.socket()
    s.connect((host, port))
    s.sendall((os.path.basename(filename) + '\n').encode('utf-8'))
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            s.sendall(chunk)
    s.close()


def handle_connection(conn, storage_dir):
    """Handle an incoming connection: read filename header then stream to disk."""
    try:
        with conn:
            header = conn.recv(1024)
            if not header:
                return
            filename = header.decode('utf-8', errors='ignore').strip()
            out_path = os.path.join(storage_dir, filename)
            os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
            with open(out_path, 'wb') as f:
                while True:
                    chunk = conn.recv(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
    except Exception:
        # keep handler robust for simple demo usage
        return


def create_server_socket(bind_host='', bind_port=0, backlog=5):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind_host, bind_port))
    s.listen(backlog)
    return s
