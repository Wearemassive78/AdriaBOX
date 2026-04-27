import argparse
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import requests
import socket
from common.tcp import send_file
from common.constants import DEFAULT_METADATA_URL, DEFAULT_NODE_HOST, DEFAULT_NODE_TCP_PORT
def send_file_to_node(host, port, filename):
    return send_file(host, port, filename)

def register_metadata(metadata_url, filename, chunks=1):
    r = requests.post(f"{metadata_url}/store", json={'filename': filename, 'chunks': chunks})
    r.raise_for_status()
    return r.json()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--metadata', default=DEFAULT_METADATA_URL)
    parser.add_argument('--node-host', default=DEFAULT_NODE_HOST)
    parser.add_argument('--node-tcp-port', type=int, default=DEFAULT_NODE_TCP_PORT)
    args = parser.parse_args()
    # naive single-node upload
    #info = register_metadata(args.metadata, os.path.basename(args.file), chunks=1)
    #print('Registered metadata:', info)
    send_file_to_node(args.node_host, args.node_tcp_port, args.file)
    print('File sent to storage node')
