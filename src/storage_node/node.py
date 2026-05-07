import argparse
import socket
import threading
import os
import time
import requests
from flask import Flask, jsonify
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)

NODE_ID = os.environ.get('ADRIABOX_NODE_ID', 'storage-node')
NODE_HOST = os.environ.get('ADRIABOX_NODE_HOST', NODE_ID)
METADATA_URL = os.environ.get('ADRIABOX_METADATA_URL')
DATA_DIR = os.environ.get(
    'ADRIABOX_DATA_DIR',
    os.path.join(os.path.dirname(__file__), 'data')
)
os.makedirs(DATA_DIR, exist_ok=True)

def handle_tcp_client(conn, addr, storage_dir=DATA_DIR):
    # Delegate to common handler to keep protocol consistent
    from common.tcp import handle_connection
    return handle_connection(conn, storage_dir)

def run_tcp_server(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)
    print(f"Storage node TCP listening on {host}:{port}")
    try:
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True).start()
    finally:
        s.close()

def register_with_metadata(http_port, tcp_port, retries=10, delay=1.0):
    """Registers this storage node with the metadata server when configured."""
    if not METADATA_URL:
        print("Metadata registration skipped: ADRIABOX_METADATA_URL is not set")
        return False

    payload = {
        'node_id': NODE_ID,
        'host': NODE_HOST,
        'http_port': http_port,
        'tcp_port': tcp_port,
        'status': 'active',
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(f"{METADATA_URL}/nodes", json=payload, timeout=3)
            response.raise_for_status()
            print(f"Registered storage node {NODE_ID} with metadata server")
            return True
        except requests.RequestException as exc:
            print(f"Node registration attempt {attempt}/{retries} failed: {exc}")
            time.sleep(delay)

    return False

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'node_id': NODE_ID, 'metadata_url': METADATA_URL})

@app.route('/info')
def info():
    return jsonify({
        'node_id': NODE_ID,
        'data_dir': DATA_DIR,
        'files_count': len(os.listdir(DATA_DIR)),
    })

@app.route('/files')
def files():
    items = os.listdir(DATA_DIR)
    return jsonify(items)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--tcp-port', type=int, default=7001)
    parser.add_argument('--http-port', type=int, default=6001)
    args = parser.parse_args()
    threading.Thread(target=run_tcp_server, args=(args.host, args.tcp_port), daemon=True).start()
    register_with_metadata(args.http_port, args.tcp_port)
    app.run(host=args.host, port=args.http_port)
