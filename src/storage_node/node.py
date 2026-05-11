import argparse
import os
import socket
import sys
import threading

from flask import Flask, jsonify

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.tcp import handle_connection


app = Flask(__name__)

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_DIR = os.environ.get("ADRIABOX_STORAGE_DIR", DEFAULT_DATA_DIR)
os.makedirs(DATA_DIR, exist_ok=True)


def handle_tcp_client(conn, addr, storage_dir=None):
    return handle_connection(conn, storage_dir or DATA_DIR)


def run_tcp_server(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    print(f"Storage node TCP listening on {host}:{port}, dir={DATA_DIR}")
    try:
        while True:
            conn, addr = sock.accept()
            threading.Thread(
                target=handle_tcp_client,
                args=(conn, addr),
                daemon=True,
            ).start()
    finally:
        sock.close()


@app.route("/health")
def health():
    return jsonify({"status": "ok", "storage_dir": DATA_DIR})


@app.route("/files")
def files():
    return jsonify(sorted(os.listdir(DATA_DIR)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--tcp-port", type=int, default=7001)
    parser.add_argument("--http-port", type=int, default=6001)
    parser.add_argument("--storage-dir", default=DATA_DIR)
    args = parser.parse_args()

    DATA_DIR = args.storage_dir
    os.makedirs(DATA_DIR, exist_ok=True)

    threading.Thread(
        target=run_tcp_server,
        args=(args.host, args.tcp_port),
        daemon=True,
    ).start()
    app.run(host=args.host, port=args.http_port)
