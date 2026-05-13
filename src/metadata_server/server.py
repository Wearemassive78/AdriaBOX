import datetime
import math
import os
import sys

from flask import Flask, jsonify, request
import jwt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.constants import CHUNK_SIZE, LOGICAL_BLOCK_SIZE
from metadata_server.db import DatabaseManager

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "metadata.db",
)

def load_storage_nodes():
    """Load storage nodes from env or return the local Docker demo topology."""
    raw_nodes = os.environ.get("ADRIABOX_STORAGE_NODES")
    if raw_nodes:
        nodes = []
        for index, item in enumerate(raw_nodes.split(","), start=1):
            parts = item.split(":")
            if len(parts) != 5:
                raise ValueError("ADRIABOX_STORAGE_NODES items must be node_id:host:tcp_port:client_host:client_tcp_port")
            node_id, host, tcp_port, client_host, client_tcp_port = parts
            nodes.append({
                "node_id": node_id,
                "host": host,
                "tcp_port": int(tcp_port),
                "client_host": client_host,
                "client_tcp_port": int(client_tcp_port),
            })
        return nodes

    return [
        {"node_id": "storage1", "host": "storage1", "tcp_port": 7001, "client_host": "127.0.0.1", "client_tcp_port": 7001},
        {"node_id": "storage2", "host": "storage2", "tcp_port": 7002, "client_host": "127.0.0.1", "client_tcp_port": 7002},
        {"node_id": "storage3", "host": "storage3", "tcp_port": 7003, "client_host": "127.0.0.1", "client_tcp_port": 7003},
    ]

class AdriaServer:
    """Master Node Web Server handling REST API requests."""

    def __init__(self, db_path=DEFAULT_DB_PATH, secret_key="super-secret-master-key-for-adriabox"):
        self.app = Flask(__name__)
        self.db = DatabaseManager(db_path)
        self.secret_key = secret_key
        self.storage_nodes = load_storage_nodes()

        self.app.add_url_rule("/health", view_func=self.health, methods=["GET"])
        self.app.add_url_rule("/register", view_func=self.register, methods=["POST"])
        self.app.add_url_rule("/login", view_func=self.login, methods=["POST"])
        self.app.add_url_rule("/upload", view_func=self.upload, methods=["POST"])
        self.app.add_url_rule("/files/upload-plan", view_func=self.create_upload_plan, methods=["POST"])
        self.app.add_url_rule("/files/complete", view_func=self.complete_upload, methods=["POST"])
        self.app.add_url_rule("/files/download-plan", view_func=self.create_download_plan, methods=["GET"])

    def _get_current_user(self):
        """Extracts and verifies the JWT token from the Authorization header."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header.split(" ")[1]
        try:
            data = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return data
        except Exception:
            return None

    def health(self):
        return jsonify({"status": "ok", "nodes": self.storage_nodes})

    def register(self):
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Missing credentials"}), 400

        try:
            self.db.register_user(username, password)
            return jsonify({"message": "User registered"}), 201
        except ValueError:
            return jsonify({"error": "Username already exists"}), 409

    def login(self):
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Missing credentials"}), 400

        user = self.db.verify_user(username, password)

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        payload = {
            "user_id": user["id"],
            "username": user["username"],
            "role": user.get("role", "user"),
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")

        return jsonify({"token": token, "username": user["username"], "role": user.get("role", "user")}), 200

    def upload(self):
        """Legacy endpoint."""
        return jsonify({"error": "Deprecated"}), 400

    def create_upload_plan(self):
        current_user = self._get_current_user()
        if not current_user:
            return jsonify({"error": "Unauthorized. Invalid or missing token."}), 401

        data = request.json or {}
        filename = data.get("filename")
        file_size = int(data.get("size") or 0)
        remote_dir = data.get("remote_dir") or "/"

        if not filename:
            return jsonify({"error": "Missing filename"}), 400
        if file_size < 0:
            return jsonify({"error": "Invalid size"}), 400

        node_count = len(self.storage_nodes)
        
        if file_size == 0:
            chunk_count = 1
        else:
            chunk_count = max(1, math.ceil(file_size / LOGICAL_BLOCK_SIZE))

        # Assign the file to the actual authenticated user
        file_id = self.db.add_file(filename, file_size, chunk_count, owner_id=current_user["user_id"])

        chunks = []
        offset = 0
        for index in range(chunk_count):
            node = self.storage_nodes[index % node_count]
            size = min(LOGICAL_BLOCK_SIZE, file_size - offset)
            if size <= 0 and index == 0:
                size = 0
                
            chunk_filename = f"{file_id}_{index}_{os.path.basename(filename)}.chunk"
            chunks.append({
                "index": index,
                "offset": offset,
                "size": size,
                "chunk_filename": chunk_filename,
                "node_id": node["node_id"],
                "host": node["host"],
                "tcp_port": node["client_tcp_port"],
                "client_host": node["client_host"],
            })
            offset += size

        return jsonify({
            "file_id": file_id,
            "filename": filename,
            "remote_path": os.path.join(remote_dir, filename).replace("\\", "/"),
            "size": file_size,
            "chunks": chunks,
        }), 200

    def create_download_plan(self):
        current_user = self._get_current_user()
        if not current_user:
            return jsonify({"error": "Unauthorized. Invalid or missing token."}), 401

        filename = request.args.get("filename")
        if not filename:
            return jsonify({"error": "Missing filename parameter"}), 400

        file_info = self.db.get_file_by_name(filename)
        if not file_info:
            return jsonify({"error": "File not found"}), 404

        # Enforce Ownership Validation
        if file_info["owner_id"] != current_user["user_id"] and current_user["role"] != "admin":
             return jsonify({"error": "Forbidden: You do not have permission to download this file."}), 403

        chunks_data = self.db.get_chunks_by_file_id(file_info["id"])
        
        plan_chunks = []
        for c in chunks_data:
            node_cfg = next((n for n in self.storage_nodes if n["node_id"] == c["node_id"]), self.storage_nodes[0])
            plan_chunks.append({
                "index": c["chunk_index"],
                "chunk_filename": c["chunk_filename"],
                "node_id": c["node_id"],
                "client_host": node_cfg["client_host"],
                "tcp_port": node_cfg["client_tcp_port"],
                "size": c["size"]
            })

        return jsonify({
            "file_id": file_info["id"],
            "filename": filename,
            "size": file_info["size"],
            "chunks": plan_chunks
        }), 200

    def complete_upload(self):
        current_user = self._get_current_user()
        if not current_user:
            return jsonify({"error": "Unauthorized. Invalid or missing token."}), 401

        data = request.json or {}
        required = ("file_id", "filename", "chunks")
        missing = [field for field in required if field not in data]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

        file_id = data["file_id"]
        
        for chunk in data["chunks"]:
            self.db.save_chunk_metadata(
                file_id=file_id,
                chunk_index=chunk["index"],
                node_id=chunk["node_id"],
                chunk_filename=chunk["chunk_filename"],
                size=chunk["size"]
            )

        return jsonify({
            "message": "Upload completed",
            "file_id": file_id,
            "filename": data["filename"],
            "remote_path": data.get("remote_path"),
            "size": data.get("size"),
            "sha256": data.get("sha256"),
            "chunks": data["chunks"],
        }), 200

    def run(self, host="0.0.0.0", port=5000):
        self.app.run(host=host, port=port, debug=True)

if __name__ == "__main__":
    server = AdriaServer()
    server.run()
