<<<<<<< HEAD
"""TCP helpers for sending and receiving files with a simple newline-framed header.

Provides `send_file` for clients and `handle_connection` for storage nodes.
"""
import os
import socket
import struct
from .constants import CHUNK_SIZE

ACK_OK = b"OK\n"
ACK_ERROR = b"ERR\n"

def recv_exact(conn, n):
    """Legge esattamente n byte dalla socket."""
    data = bytearray()
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None # Connessione chiusa prematuramente
        data.extend(packet)
    return bytes(data)
     
def send_file(host, port, filename):
    s = socket.socket()
    s.connect((host, port))


    basename = os.path.basename(filename).encode('utf-8')
    name_len = len(basename)

    file_size = os.path.getsize(filename)
    
    header = struct.pack('>I', name_len) + basename + struct.pack('>Q', file_size)
    
    s.sendall(header)
    
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            s.sendall(chunk)
            
    s.close()

def send_bytes(host, port, remote_filename, data, timeout=10.0):
    """Send an in-memory bytes payload to a storage node with a remote filename."""
    encoded_name = os.path.basename(remote_filename).encode('utf-8')
    header = struct.pack('>I', len(encoded_name)) + encoded_name + struct.pack('>Q', len(data))

    with socket.create_connection((host, port), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(header)
        if data:
            s.sendall(data)

        ack = recv_exact(s, len(ACK_OK))
        if ack != ACK_OK:
            raise ConnectionError(f"Storage node {host}:{port} did not confirm chunk write")

def handle_connection(conn, storage_dir):
    """Handle an entry connection reading the binary file."""
    try:
        with conn:
            raw_name_len = recv_exact(conn, 4)
            if not raw_name_len:
                return
            name_len = struct.unpack('>I', raw_name_len)[0]

            raw_name = recv_exact(conn, name_len)
            filename = raw_name.decode('utf-8')

            raw_file_size = recv_exact(conn, 8)
            if not raw_file_size:
                conn.sendall(ACK_ERROR)
                return
            file_size = struct.unpack('>Q', raw_file_size)[0]

            out_path = os.path.join(storage_dir, filename)
            os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

            bytes_received = 0
            with open(out_path, 'wb') as f:
                while bytes_received < file_size:
                    bytes_to_read = min(CHUNK_SIZE, file_size - bytes_received)
                    chunk = conn.recv(bytes_to_read)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_received += len(chunk)

                f.flush()
                os.fsync(f.fileno())

            if bytes_received != file_size:
                try:
                    os.remove(out_path)
                except OSError:
                    pass
                conn.sendall(ACK_ERROR)
                return

            conn.sendall(ACK_OK)

    except Exception as e:
        print(f"TCP connection error: {e}")
        try:
            conn.sendall(ACK_ERROR)
        except OSError:
            pass
        return


def create_server_socket(bind_host='', bind_port=0, backlog=5):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind_host, bind_port))
    s.listen(backlog)
    return s
=======
import os
import socket
import struct
from .constants import CHUNK_SIZE

class AdriaTCPStreamer:
    """
    Base class for handling TCP binary transfers with the AdriaBOX protocol.
    Provides low-level exact reading capabilities similar to C's recv loop.
    """
    
    @staticmethod
    def _recv_exact(conn, n):
        """Reads exactly n bytes from the socket or returns None."""
        data = bytearray()
        while len(data) < n:
            packet = conn.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)

class FileSender(AdriaTCPStreamer):
    """Encapsulates the logic for sending a file to a remote node."""
    
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def send(self, local_path):
        """
        Sends a file using the custom header protocol:
        [Name Len (4B)] + [Name (v)] + [File Size (8B)] + [Payload (v)]
        """
        file_size = os.path.getsize(local_path)
        basename = os.path.basename(local_path).encode('utf-8')
        name_len = len(basename)

        # Build the header (Big-Endian)
        header = struct.pack('>I', name_len) + basename + struct.pack('>Q', file_size)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.host, self.port))
            # Send header
            s.sendall(header)
            
            # Stream the file content in chunks to save RAM
            with open(local_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    s.sendall(chunk)

class FileReceiver(AdriaTCPStreamer):
    """Encapsulates the logic for receiving and saving a file on a storage node."""
    
    def __init__(self, connection, storage_dir):
        self.conn = connection
        self.storage_dir = storage_dir

    def receive(self):
        """Parses the header and writes the incoming binary stream to disk."""
        # 1. Read filename length
        raw_name_len = self._recv_exact(self.conn, 4)
        if not raw_name_len: return
        name_len = struct.unpack('>I', raw_name_len)[0]

        # 2. Read filename
        raw_name = self._recv_exact(self.conn, name_len)
        filename = raw_name.decode('utf-8')

        # 3. Read total file size
        raw_file_size = self._recv_exact(self.conn, 8)
        file_size = struct.unpack('>Q', raw_file_size)[0]

        # Prepare output path
        out_path = os.path.join(self.storage_dir, filename)
        os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

        # 4. Read payload and write to disk
        bytes_received = 0
        with open(out_path, 'wb') as f:
            while bytes_received < file_size:
                bytes_to_read = min(CHUNK_SIZE, file_size - bytes_received)
                chunk = self.conn.recv(bytes_to_read)
                if not chunk:
                    break
                f.write(chunk)
                bytes_received += len(chunk)


>>>>>>> bcfa2ad0976403e7a9339737e408c22a1e90c352
