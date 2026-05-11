"""TCP helpers for sending and receiving files via AdriaBOX custom protocol."""
import os
import socket
import struct
from .constants import CHUNK_SIZE

class AdriaTCPStreamer:
    """Base class for TCP binary transfers with the AdriaBOX protocol."""
    
    # Sam's new acknowledgment constants
    ACK_OK = b"OK\n"
    ACK_ERROR = b"ERR\n"

    @staticmethod
    def _recv_exact(conn, n):
        """Legge esattamente n byte dalla socket."""
        data = bytearray()
        while len(data) < n:
            packet = conn.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)

class FileSender(AdriaTCPStreamer):
    """Encapsulates the logic for sending a file to a remote node."""
    
    def __init__(self, host, port, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, local_path):
        """Sends a file using the custom header and waits for ACK."""
        file_size = os.path.getsize(local_path)
        basename = os.path.basename(local_path).encode('utf-8')
        name_len = len(basename)

        header = struct.pack('>I', name_len) + basename + struct.pack('>Q', file_size)

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            
            with open(local_path, 'rb') as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    s.sendall(chunk)
            
            # Wait for Sam's new acknowledgment mechanism
            ack = self._recv_exact(s, len(self.ACK_OK))
            if ack != self.ACK_OK:
                raise ConnectionError(f"Storage node {self.host}:{self.port} did not confirm write")

class BytesSender(AdriaTCPStreamer):
    """Encapsulates the logic for sending in-memory bytes (Sam's new addition)."""
    
    def __init__(self, host, port, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, remote_filename, data):
        """Sends raw bytes from memory."""
        encoded_name = os.path.basename(remote_filename).encode('utf-8')
        header = struct.pack('>I', len(encoded_name)) + encoded_name + struct.pack('>Q', len(data))

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            if data:
                s.sendall(data)

            ack = self._recv_exact(s, len(self.ACK_OK))
            if ack != self.ACK_OK:
                raise ConnectionError(f"Storage node {self.host}:{self.port} did not confirm chunk write")

class FileReceiver(AdriaTCPStreamer):
    """Encapsulates the logic for receiving and saving a file on a storage node."""
    
    def __init__(self, connection, storage_dir):
        self.conn = connection
        self.storage_dir = storage_dir

    def receive(self):
        """Parses the header, writes to disk, verifies size, and sends ACK."""
        try:
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

                # Sam's safety additions
                f.flush()
                os.fsync(f.fileno())

            # Verification
            if bytes_received != file_size:
                try:
                    os.remove(out_path)
                except OSError:
                    pass
                self.conn.sendall(self.ACK_ERROR)
                return

            self.conn.sendall(self.ACK_OK)

        except Exception as e:
            print(f"TCP connection error: {e}")
            try:
                self.conn.sendall(self.ACK_ERROR)
            except OSError:
                pass

def create_server_socket(bind_host='', bind_port=0, backlog=5):
    """Legacy helper maintained for node.py compatibility."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind_host, bind_port))
    s.listen(backlog)
    return s
