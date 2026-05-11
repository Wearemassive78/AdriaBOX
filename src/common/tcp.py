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


