import argparse
import socket
import threading
import os
from flask import Flask, jsonify
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
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

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

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
    app.run(host=args.host, port=args.http_port)
