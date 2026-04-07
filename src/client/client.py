import argparse
import requests
import socket
import os

def send_file_to_node(host, port, filename):
    s = socket.socket()
    s.connect((host, port))
    # send filename as first packet
    s.sendall((os.path.basename(filename) + '\n').encode('utf-8'))
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            s.sendall(chunk)
    s.close()

def register_metadata(metadata_url, filename, chunks=1):
    r = requests.post(f"{metadata_url}/store", json={'filename': filename, 'chunks': chunks})
    r.raise_for_status()
    return r.json()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--metadata', default='http://localhost:5000')
    parser.add_argument('--node-host', default='localhost')
    parser.add_argument('--node-tcp-port', type=int, default=7001)
    args = parser.parse_args()
    # naive single-node upload
    info = register_metadata(args.metadata, os.path.basename(args.file), chunks=1)
    print('Registered metadata:', info)
    send_file_to_node(args.node_host, args.node_tcp_port, args.file)
    print('File sent to storage node')
