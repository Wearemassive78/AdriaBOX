"""TCP helpers for AdriaBOX file transfers."""
import os
import socket
import struct

from .constants import CHUNK_SIZE

ACK_OK = b"OK\n"
ACK_ERROR = b"ERR\n"


def recv_exact(conn, n):
    """Read exactly n bytes from a socket, or None if the peer closes early."""
    data = bytearray()
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)


def send_bytes(host, port, remote_filename, data, timeout=10.0):
    """Send an in-memory payload to a storage node and wait for its ACK."""
    encoded_name = os.path.basename(remote_filename).encode("utf-8")
    header = (
        struct.pack(">I", len(encoded_name))
        + encoded_name
        + struct.pack(">Q", len(data))
    )

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(header)
        if data:
            sock.sendall(data)

        ack = recv_exact(sock, len(ACK_OK))
        if ack != ACK_OK:
            raise ConnectionError(
                f"Storage node {host}:{port} did not confirm chunk write"
            )


def send_file(host, port, filename, remote_filename=None, timeout=10.0):
    """Send a whole local file to a storage node."""
    remote_filename = remote_filename or os.path.basename(filename)
    with open(filename, "rb") as source:
        send_bytes(host, port, remote_filename, source.read(), timeout=timeout)


def handle_connection(conn, storage_dir):
    """Receive one file/chunk from a client and persist it under storage_dir."""
    try:
        with conn:
            raw_name_len = recv_exact(conn, 4)
            if not raw_name_len:
                return

            name_len = struct.unpack(">I", raw_name_len)[0]
            raw_name = recv_exact(conn, name_len)
            if not raw_name:
                conn.sendall(ACK_ERROR)
                return

            raw_file_size = recv_exact(conn, 8)
            if not raw_file_size:
                conn.sendall(ACK_ERROR)
                return

            filename = os.path.basename(raw_name.decode("utf-8"))
            file_size = struct.unpack(">Q", raw_file_size)[0]
            out_path = os.path.join(storage_dir, filename)
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

            bytes_received = 0
            with open(out_path, "wb") as dest:
                while bytes_received < file_size:
                    bytes_to_read = min(CHUNK_SIZE, file_size - bytes_received)
                    chunk = conn.recv(bytes_to_read)
                    if not chunk:
                        break
                    dest.write(chunk)
                    bytes_received += len(chunk)
                dest.flush()
                os.fsync(dest.fileno())

            if bytes_received != file_size:
                try:
                    os.remove(out_path)
                except OSError:
                    pass
                conn.sendall(ACK_ERROR)
                return

            conn.sendall(ACK_OK)
    except Exception as exc:
        print(f"TCP connection error: {exc}")
        try:
            conn.sendall(ACK_ERROR)
        except OSError:
            pass


def create_server_socket(bind_host="", bind_port=0, backlog=5):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind_host, bind_port))
    sock.listen(backlog)
    return sock


class FileSender:
    """Compatibility wrapper around send_file."""

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def send(self, local_path):
        return send_file(self.host, self.port, local_path)


class FileReceiver:
    """Compatibility wrapper around handle_connection."""

    def __init__(self, connection, storage_dir):
        self.conn = connection
        self.storage_dir = storage_dir

    def receive(self):
        return handle_connection(self.conn, self.storage_dir)
