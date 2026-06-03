"""Low-level TCP protocol engine for high-performance binary block streaming."""
import socket
import struct
import json
import os

class AdriaTCPStreamer:
    """Base network component providing strict byte extraction wrappers over TCP sockets."""
    ACK_OK = b"ACK_OK"
    ACK_ERROR = b"ACK_ERR"

    def _recv_exact(self, sock: socket.socket, num_bytes: int) -> bytearray:
        """Ensure exact extraction of N bytes from the socket buffer, preventing fragmentation truncation."""
        data = bytearray()
        while len(data) < num_bytes:
            packet = sock.recv(num_bytes - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data


class ChunkStreamSender(AdriaTCPStreamer):
    """Client-side or Node-side TCP streamer that forwards a chunk with its replication pipeline."""
    def __init__(self, host: str, port: int, timeout=10.0, crypto_key=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.crypto_key = crypto_key

    def send_with_pipeline(self, file_stream, chunk_filename: str, chunk_size: int, pipeline: list) -> bool:
        """Inject the serialization meta-header and stream raw bytes down the synchronous replication cascade."""
        metadata = {"chunk_filename": chunk_filename, "pipeline": pipeline}
        metadata_bytes = json.dumps(metadata).encode('utf-8')
        
        # Protocol payload: 'U' (Upload command) + Meta Len (4B) + Data Size (4B) + Meta JSON + Stream
        header = b'U' + struct.pack('>II', len(metadata_bytes), chunk_size) + metadata_bytes

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            
            bytes_sent = 0
            while bytes_sent < chunk_size:
                buffer = file_stream.read(min(4096, chunk_size - bytes_sent))
                if not buffer:
                    break
                s.sendall(buffer)
                bytes_sent += len(buffer)
                
            # Block and await cascading ACK bubble-up verification
            ack = self._recv_exact(s, len(self.ACK_OK))
            return ack == self.ACK_OK


class ChunkDownloader(AdriaTCPStreamer):
    """Client-side receiver component targeting a specific replica node to download content blocks."""
    def __init__(self, host: str, port: int, timeout=10.0, crypto_key=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.crypto_key = crypto_key

    def download(self, chunk_filename: str, dest_file_stream, chunk_size: int):
        """Invoke 'D' command to pull raw binary data blocks directly into the destination file layout."""
        filename_bytes = chunk_filename.encode('utf-8')
        header = b'D' + struct.pack('>I', len(filename_bytes)) + filename_bytes

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            
            bytes_received = 0
            while bytes_received < chunk_size:
                buffer = s.recv(min(4096, chunk_size - bytes_received))
                if not buffer:
                    raise IOError("Connection severed midway during chunk download execution.")
                dest_file_stream.write(buffer)
                bytes_received += len(buffer)


class ChunkDeleter(AdriaTCPStreamer):
    """Asynchronous best-effort network cleaner to dispatch physical storage erasure signals."""
    def __init__(self, host: str, port: int, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def delete(self, chunk_filename: str):
        """Invoke 'X' command to wipe the unlinked file block entry from physical storage."""
        filename_bytes = chunk_filename.encode('utf-8')
        header = b'X' + struct.pack('>I', len(filename_bytes)) + filename_bytes
        
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)


class FileReceiver(AdriaTCPStreamer):
    """Multi-tenant node engine handling chunk staging, telemetry forwarding, and block synchronization."""
    def __init__(self, conn: socket.socket, storage_dir: str, crypto_key=None):
        self.conn = conn
        self.storage_dir = storage_dir
        self.crypto_key = crypto_key

    def serve(self):
        """Parse incoming primitive header commands to route session connections."""
        try:
            cmd = self._recv_exact(self.conn, 1)
            if cmd == b'U': self.handle_pipeline_upload()
            elif cmd == b'D': self.handle_download()
            elif cmd == b'X': self.handle_delete()
            else: self.conn.sendall(self.ACK_ERROR)
        except Exception as e:
            print(f"[Error] Protocol execution failure: {e}")
            try: self.conn.sendall(self.ACK_ERROR)
            except OSError: pass
        finally:
            try: self.conn.close()
            except OSError: pass

    def handle_pipeline_upload(self):
        """Tee-streaming pipeline engine writing locally while concurrently pushing blocks down the cluster network."""
        lengths = self._recv_exact(self.conn, 8)
        if not lengths: return
        meta_len, chunk_size = struct.unpack('>II', lengths)

        meta_bytes = self._recv_exact(self.conn, meta_len)
        metadata = json.loads(meta_bytes.decode('utf-8'))
        
        chunk_filename = metadata["chunk_filename"]
        pipeline = metadata["pipeline"]

        file_path = os.path.join(self.storage_dir, chunk_filename)
        next_node_socket = None
        pipeline_failed = False

        # If a downstream target replica is available, initialize the next pipe socket link
        if pipeline:
            try:
                next_node = pipeline[0]
                remaining_pipeline = pipeline[1:]
                
                next_metadata = {"chunk_filename": chunk_filename, "pipeline": remaining_pipeline}
                next_meta_bytes = json.dumps(next_metadata).encode('utf-8')
                next_header = b'U' + struct.pack('>II', len(next_meta_bytes), chunk_size) + next_meta_bytes
                
                next_node_socket = socket.create_connection((next_node["host"], int(next_node["tcp_port"])), timeout=10.0)
                next_node_socket.sendall(next_header)
            except Exception as e:
                print(f"[Warning] Downstream pipeline connection block failed: {e}")
                pipeline_failed = True

        bytes_received = 0
        with open(file_path, "wb") as f:
            while bytes_received < chunk_size:
                buffer = self.conn.recv(min(4096, chunk_size - bytes_received))
                if not buffer: break
                
                f.write(buffer) # Local write
                if next_node_socket and not pipeline_failed:
                    try: next_node_socket.sendall(buffer) # Inline pipeline pass
                    except OSError: pipeline_failed = True
                        
                bytes_received += len(buffer)

        # Coordinate cascading verification
        if next_node_socket and not pipeline_failed:
            try:
                ack = next_node_socket.recv(len(self.ACK_OK))
                next_node_socket.close()
                self.conn.sendall(self.ACK_OK if ack == self.ACK_OK else self.ACK_ERROR)
            except Exception:
                self.conn.sendall(self.ACK_ERROR)
        else:
            self.conn.sendall(self.ACK_ERROR if pipeline_failed else self.ACK_OK)

    def handle_download(self):
        """Locate raw block assets on disk and push data streams backward up the socket link."""
        len_bytes = self._recv_exact(self.conn, 4)
        if not len_bytes: return
        filename_len = struct.unpack('>I', len_bytes)[0]
        
        chunk_filename = self._recv_exact(self.conn, filename_len).decode('utf-8')
        file_path = os.path.join(self.storage_dir, chunk_filename)
        
        if not os.path.exists(file_path):
            self.conn.sendall(self.ACK_ERROR)
            return

        with open(file_path, "rb") as f:
            while True:
                buffer = f.read(4096)
                if not buffer: break
                self.conn.sendall(buffer)

    def handle_delete(self):
        """Unlink block targets from the physical disk topology."""
        len_bytes = self._recv_exact(self.conn, 4)
        if not len_bytes: return
        filename_len = struct.unpack('>I', len_bytes)[0]
        
        chunk_filename = self._recv_exact(self.conn, filename_len).decode('utf-8')
        file_path = os.path.join(self.storage_dir, chunk_filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)

