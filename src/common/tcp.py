"""TCP helpers for sending and receiving files via AdriaBOX custom protocol."""
import hashlib
import os
import socket
import struct
from .constants import CHUNK_SIZE

class AdriaTCPStreamer:
    """Base class for TCP binary transfers with the AdriaBOX protocol."""
    ACK_OK = b"OK\n"
    ACK_ERROR = b"ERR\n"

    @staticmethod
    def _recv_exact(conn, n):
        """Reads exactly n bytes from the socket."""
        data = bytearray()
        while len(data) < n:
            packet = conn.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)

class ChunkStreamSender(AdriaTCPStreamer):
    """Encapsulates the logic for streaming a specific block of a file to a node."""

    def __init__(self, host, port, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, file_descriptor, remote_filename, size_to_send):
        """Streams exactly 'size_to_send' bytes and calculates SHA-256 on the fly."""
        encoded_name = os.path.basename(remote_filename).encode('utf-8')
        # ADDED 'U' FOR UPLOAD COMMAND
        header = b'U' + struct.pack('>I', len(encoded_name)) + encoded_name + struct.pack('>Q', size_to_send)
        
        hasher = hashlib.sha256()

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            
            bytes_sent = 0
            while bytes_sent < size_to_send:
                read_size = min(CHUNK_SIZE, size_to_send - bytes_sent)
                data = file_descriptor.read(read_size)
                if not data:
                    break
                
                hasher.update(data)
                s.sendall(data)
                bytes_sent += len(data)

            ack = self._recv_exact(s, len(self.ACK_OK))
            if ack != self.ACK_OK:
                raise ConnectionError(f"Storage node {self.host}:{self.port} did not confirm chunk write")
            
            return hasher.hexdigest()

class ChunkDownloader(AdriaTCPStreamer):
    """Client-side class to request and download a chunk from a storage node."""

    def __init__(self, host, port, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def download(self, chunk_filename, file_descriptor, expected_size):
        """Requests a file from the node and writes it to an open file descriptor."""
        encoded_name = chunk_filename.encode('utf-8')
        # ADDED 'D' FOR DOWNLOAD COMMAND
        header = b'D' + struct.pack('>I', len(encoded_name)) + encoded_name

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            
            bytes_received = 0
            while bytes_received < expected_size:
                to_read = min(CHUNK_SIZE, expected_size - bytes_received)
                packet = s.recv(to_read)
                if not packet:
                    break
                file_descriptor.write(packet)
                bytes_received += len(packet)
            
            if bytes_received != expected_size:
                raise ConnectionError("Connection dropped before chunk was fully downloaded")
            return True

class FileReceiver(AdriaTCPStreamer):
    """Encapsulates the logic for receiving and sending chunks on a storage node."""
    
    def __init__(self, connection, storage_dir):
        self.conn = connection
        self.storage_dir = storage_dir

    def serve(self):
        """Dispatcher: reads the first byte to decide between Upload (U) or Download (D)."""
        try:
            cmd = self._recv_exact(self.conn, 1)
            if cmd == b'U':
                self.handle_upload()
            elif cmd == b'D':
                self.handle_download()
            else:
                self.conn.sendall(self.ACK_ERROR)
        except Exception as e:
            print(f"TCP protocol error: {e}")
            try:
                self.conn.sendall(self.ACK_ERROR)
            except OSError:
                pass

    def handle_upload(self):
        """Processes incoming data and saves it to disk."""
        raw_name_len = self._recv_exact(self.conn, 4)
        if not raw_name_len: return
        name_len = struct.unpack('>I', raw_name_len)[0]

        raw_name = self._recv_exact(self.conn, name_len)
        filename = raw_name.decode('utf-8')

        raw_file_size = self._recv_exact(self.conn, 8)
        if not raw_file_size:
            self.conn.sendall(self.ACK_ERROR)
            return
        file_size = struct.unpack('>Q', raw_file_size)[0]

        out_path = os.path.join(self.storage_dir, filename)
        os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

        bytes_received = 0
        with open(out_path, 'wb') as f:
            while bytes_received < file_size:
                bytes_to_read = min(CHUNK_SIZE, file_size - bytes_received)
                chunk = self.conn.recv(bytes_to_read)
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
            self.conn.sendall(self.ACK_ERROR)
            return

        self.conn.sendall(self.ACK_OK)

    def handle_download(self):
        """Reads a requested chunk from disk and streams it to the client."""
        raw_name_len = self._recv_exact(self.conn, 4)
        if not raw_name_len: return
        name_len = struct.unpack('>I', raw_name_len)[0]

        raw_name = self._recv_exact(self.conn, name_len)
        filename = raw_name.decode('utf-8')
        
        file_path = os.path.join(self.storage_dir, filename)
        if not os.path.exists(file_path):
            return
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                self.conn.sendall(chunk)

def create_server_socket(bind_host='', bind_port=0, backlog=5):
    """Legacy helper maintained for testing compatibility."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind_host, bind_port))
    s.listen(backlog)
    return s
