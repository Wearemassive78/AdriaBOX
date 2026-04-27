import argparse
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import requests
import socket
from common.tcp import send_file
from common.constants import DEFAULT_METADATA_URL, DEFAULT_NODE_HOST, DEFAULT_NODE_TCP_PORT
try:
    from client.interactive import run_interactive
except Exception:
    # Fallback when running client.py as a script (client is not a package)
    from interactive import run_interactive

    
def send_file_to_node(host, port, filename):
    return send_file(host, port, filename)

def register_metadata(metadata_url, filename, chunks=1):
    r = requests.post(f"{metadata_url}/store", json={'filename': filename, 'chunks': chunks})
    r.raise_for_status()
    return r.json()

def upload_file_to_metadata(metadata_url, filepath):
    """Uploads the actual file to the metadata server's /upload endpoint."""
    with open(filepath, 'rb') as fh:
        files = {'file': (os.path.basename(filepath), fh)}
        r = requests.post(f"{metadata_url}/upload", files=files)
    r.raise_for_status()
    return r.json()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file')
    parser.add_argument('--metadata', default=DEFAULT_METADATA_URL)
    parser.add_argument('--node-host', default=DEFAULT_NODE_HOST)
    parser.add_argument('--node-tcp-port', type=int, default=DEFAULT_NODE_TCP_PORT)
    parser.add_argument('--interactive', action='store_true', help='Start interactive welcome menu')
    args = parser.parse_args()

    if args.interactive or not args.file:
        run_interactive(upload_file_to_metadata, register_metadata, send_file_to_node,
                        args.metadata, args.node_host, args.node_tcp_port)
    else:
        # Non-interactive single operation: upload then send
        try:
            info = upload_file_to_metadata(args.metadata, args.file)
            print('Metadata server saved file:', info)
        except Exception as e:
            print('Warning: failed to upload to metadata server:', e)
        send_file_to_node(args.node_host, args.node_tcp_port, args.file)
        print('File sent to storage node')