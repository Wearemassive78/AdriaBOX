"""TCP helpers for sending and receiving files with a simple newline-framed header.

Provides `send_file` for clients and `handle_connection` for storage nodes.
"""
import os
import socket
import struct
from .constants import CHUNK_SIZE

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
                    
    except Exception as e:
        print(f"TCP connection error: {e}")
        return


def create_server_socket(bind_host='', bind_port=0, backlog=5):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((bind_host, bind_port))
    s.listen(backlog)
    return s
