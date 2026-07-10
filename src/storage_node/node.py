"""Concurrent multi-threaded background daemon for AdriaBOX physical storage nodes."""
import argparse
import socket
import threading
import os
from common.tcp import FileReceiver

def handle_client_connection(conn: socket.socket, storage_dir: str):
    """Isolate the connection context inside a dedicated execution thread context."""
    receiver = FileReceiver(conn, storage_dir)
    receiver.serve()

def main():
    parser = argparse.ArgumentParser(description="AdriaBOX Distributed Storage Node Runtime daemon.")
    parser.add_argument("--host", default="0.0.0.0", help="Network binding interface topology setup.")
    parser.add_argument("--tcp-port", type=int, required=True, help="Network target entry TCP port assignment.")
    parser.add_argument("--storage-dir", required=True, help="Target isolated physical partition location root mapping.")
    args = parser.parse_args()

    os.makedirs(args.storage_dir, exist_ok=True)
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((args.host, args.tcp_port))
        server_socket.listen(128) # High capacity backlog threshold allocation
        print(f"[Active] AdriaBOX Storage Server listening on TCP interface {args.host}:{args.tcp_port}")
        
        while True:
            conn, addr = server_socket.accept()
            # Spawning an independent parallel worker thread to maintain stateless non-blocking operations
            client_thread = threading.Thread(
                target=handle_client_connection,
                args=(conn, args.storage_dir),
                daemon=True
            )
            client_thread.start()
            
    except Exception as e:
        print(f"[Critical Fault] Storage server engine crashed unexpectedly: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()

