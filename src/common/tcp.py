import socket
import struct
import json
import os

class AdriaTCPStreamer:
    """Base class providing common TCP utilities for AdriaBOX streaming protocol."""
    ACK_OK = b'OK'
    ACK_ERROR = b'ERR'

    def _recv_exact(self, sock, length):
        """Ensures exactly 'length' bytes are read from the socket."""
        data = b''
        while len(data) < length:
            packet = sock.recv(length - len(data))
            if not packet:
                return None
            data += packet
        return data


class ChunkStreamSender(AdriaTCPStreamer):
    """
    Client-side or Node-side TCP streamer that forwards a chunk 
    along with its replication pipeline metadata.
    """
    def __init__(self, host, port, timeout=10.0, crypto_key=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.crypto_key = crypto_key
        
    def send_with_pipeline(self, file_stream, chunk_filename, chunk_size, pipeline):
        """
        Sends the chunk data to the primary node, injecting the downstream
        pipeline targets for recursive replication.
        """
        # 1. Build the replication metadata header
        metadata = {
            "chunk_filename": chunk_filename,
            "pipeline": pipeline
        }
        metadata_bytes = json.dumps(metadata).encode('utf-8')
        
        # 2. Protocol Header: Command 'U' + Meta Length + Meta Bytes + Data Size
        header = b'U' + struct.pack('>II', len(metadata_bytes), chunk_size) + metadata_bytes

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            
            # 3. Stream the raw data chunks
            bytes_sent = 0
            while bytes_sent < chunk_size:
                chunk = file_stream.read(min(4096, chunk_size - bytes_sent))
                if not chunk:
                    break
                s.sendall(chunk)
                bytes_sent += len(chunk)
                
            # 4. Wait for the cascade ACK to bubble back up
            ack = self._recv_exact(s, len(self.ACK_OK))
            return ack == self.ACK_OK


class ChunkDownloader(AdriaTCPStreamer):
    """Client-side TCP streamer to retrieve a chunk from a storage node."""
    def __init__(self, host, port, timeout=10.0, crypto_key=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.crypto_key = crypto_key

    def download(self, chunk_filename, dest_file, chunk_size):
        encoded_name = chunk_filename.encode('utf-8')
        header = b'D' + struct.pack('>I', len(encoded_name)) + encoded_name
        
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            bytes_received = 0
            while bytes_received < chunk_size:
                buffer = s.recv(min(4096, chunk_size - bytes_received))
                if not buffer:
                    break
                dest_file.write(buffer)
                bytes_received += len(buffer)


class ChunkDeleter(AdriaTCPStreamer):
    """Client-side TCP streamer to send a delete command to a storage node."""
    def __init__(self, host, port, timeout=5.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def delete(self, chunk_filename):
        encoded_name = chunk_filename.encode('utf-8')
        header = b'X' + struct.pack('>I', len(encoded_name)) + encoded_name

        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall(header)
            ack = self._recv_exact(s, len(self.ACK_OK))
            return ack == self.ACK_OK


class FileReceiver(AdriaTCPStreamer):
    """
    Server-side TCP handler that processes uploads, saves data locally,
    and dynamically forwards streaming bytes to the next pipeline replica node.
    """
    def __init__(self, conn, storage_dir, crypto_key=None):
        self.conn = conn
        self.storage_dir = storage_dir
        self.crypto_key = crypto_key

    def serve(self):
        try:
            cmd = self._recv_exact(self.conn, 1)
            if cmd == b'U':
                self.handle_pipeline_upload()
            elif cmd == b'D':
                self.handle_download()
            elif cmd == b'X':
                self.handle_delete()
            else:
                self.conn.sendall(self.ACK_ERROR)
        except Exception as e:
            print(f"TCP protocol execution error: {e}")
            try: self.conn.sendall(self.ACK_ERROR)
            except OSError: pass

    def handle_pipeline_upload(self):
        """
        Receives metadata and file stream. If downstream replicas exist, 
        it simultaneously writes to disk and streams to the next node.
        """
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

        if pipeline and not pipeline_failed:
            try:
                next_node = pipeline[0]
                remaining_pipeline = pipeline[1:]
                
                next_metadata = {"chunk_filename": chunk_filename, "pipeline": remaining_pipeline}
                next_meta_bytes = json.dumps(next_metadata).encode('utf-8')
                next_header = b'U' + struct.pack('>II', len(next_meta_bytes), chunk_size) + next_meta_bytes
                
                next_node_socket = socket.create_connection((next_node["host"], int(next_node["tcp_port"])), timeout=10.0)
                next_node_socket.sendall(next_header)
            except Exception as e:
                print(f"Failed to initialize downstream replication to {next_node.get('node_id')}: {e}")
                pipeline_failed = True

        bytes_received = 0
        with open(file_path, "wb") as f:
            while bytes_received < chunk_size:
                buffer = self.conn.recv(min(4096, chunk_size - bytes_received))
                if not buffer:
                    break
                
                f.write(buffer)
                
                if next_node_socket and not pipeline_failed:
                    try:
                        next_node_socket.sendall(buffer)
                    except OSError:
                        pipeline_failed = True
                        
                bytes_received += len(buffer)

        if next_node_socket and not pipeline_failed:
            try:
                ack = next_node_socket.recv(len(self.ACK_OK))
                next_node_socket.close()
                if ack == self.ACK_OK:
                    self.conn.sendall(self.ACK_OK)
                else:
                    self.conn.sendall(self.ACK_ERROR)
            except Exception:
                self.conn.sendall(self.ACK_ERROR)
        else:
            if pipeline_failed:
                self.conn.sendall(self.ACK_ERROR)
            else:
                self.conn.sendall(self.ACK_OK)

    def handle_download(self):
        """Streams a requested chunk back to the client."""
        try:
            raw_name_len = self._recv_exact(self.conn, 4)
            if not raw_name_len: return
            name_len = struct.unpack('>I', raw_name_len)[0]
            
            raw_name = self._recv_exact(self.conn, name_len)
            filename = raw_name.decode('utf-8')
            
            file_path = os.path.join(self.storage_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        self.conn.sendall(chunk)
        except Exception as e:
            print(f"Error during download handle: {e}")

    def handle_delete(self):
        """Physically removes a chunk from the storage disk."""
        try:
            raw_name_len = self._recv_exact(self.conn, 4)
            if not raw_name_len: return
            name_len = struct.unpack('>I', raw_name_len)[0]

            raw_name = self._recv_exact(self.conn, name_len)
            filename = raw_name.decode('utf-8')
            
            file_path = os.path.join(self.storage_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                
            self.conn.sendall(self.ACK_OK)
        except Exception as e:
            print(f"Error during delete handle: {e}")
            try: self.conn.sendall(self.ACK_ERROR)
            except OSError: pass

