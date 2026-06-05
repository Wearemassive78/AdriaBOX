"""Business logic engine for the AdriaBOX Metadata Controller."""
import os
import math
import jwt
from datetime import datetime, timedelta
from metadata_server.db import DatabaseManager
from common.constants import LOGICAL_BLOCK_SIZE

SECRET_KEY = "adriabox_secret_signature_key_change_in_production"

class AdriaMetadataManager:
    def __init__(self, db_path="data/metadata.db", storage_nodes_cfg=""):
        self.db = DatabaseManager(db_path)
        self.storage_nodes = self._parse_storage_nodes(storage_nodes_cfg)

    def _parse_storage_nodes(self, cfg_string: str) -> list:
        if not cfg_string: return []
        nodes = []
        for item in cfg_string.split(","):
            parts = item.split(":")
            if len(parts) == 5:
                nodes.append({
                    "node_id": parts[0], "host": parts[1], "tcp_port": int(parts[2]),
                    "client_host": parts[3], "client_tcp_port": int(parts[4])
                })
        return nodes

    def generate_token(self, username: str) -> str:
        user = self.db.get_user_by_username(username)
        if not user: raise ValueError("User missing.")
        payload = {
            "user_id": user["id"], "username": username, "role": user["role"],
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    def authorize_request(self, auth_header: str) -> dict:
        if not auth_header or not auth_header.startswith("Bearer "):
            raise PermissionError("Missing or malformed Authorization token.")
        token = auth_header.split(" ")[1]
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError: raise PermissionError("Session expired.")
        except jwt.InvalidTokenError: raise PermissionError("Token corruption detected.")

    def build_upload_plan(self, user_ctx: dict, filename: str, file_size: int, remote_dir: str) -> dict:
        if len(self.storage_nodes) < 3: raise RuntimeError("At least 3 nodes required.")
        full_path = os.path.join(remote_dir, filename).replace("\\", "/")
        if not full_path.startswith("/"): full_path = "/" + full_path

        chunk_count = 1 if file_size == 0 else max(1, math.ceil(file_size / LOGICAL_BLOCK_SIZE))
        file_id = self.db.add_file(full_path, file_size, chunk_count, owner_id=user_ctx["user_id"])

        chunks, offset, node_count = [], 0, len(self.storage_nodes)
        for index in range(chunk_count):
            size = min(LOGICAL_BLOCK_SIZE, file_size - offset)
            if size <= 0 and index == 0: size = 0
            chunk_filename = f"{file_id}_{index}_{os.path.basename(filename)}.chunk"
            
            n1 = self.storage_nodes[index % node_count]
            n2 = self.storage_nodes[(index + 1) % node_count]
            n3 = self.storage_nodes[(index + 2) % node_count]

            chunks.append({
                "index": index, "offset": offset, "size": size, "chunk_filename": chunk_filename,
                "primary_node": {
                    "node_id": n1["node_id"], "client_host": n1["client_host"], "tcp_port": n1["client_tcp_port"]
                },
                "pipeline": [
                    {"node_id": n2["node_id"], "host": n2["host"], "tcp_port": n2["tcp_port"]},
                    {"node_id": n3["node_id"], "host": n3["host"], "tcp_port": n3["tcp_port"]}
                ]
            })
            offset += size
        return {"file_id": file_id, "remote_path": full_path, "chunks": chunks}

    def build_download_plan(self, user_ctx: dict, filename: str) -> dict:
        if not filename.startswith("/"): filename = "/" + filename
        file_info = self.db.get_file_by_name(filename)
        if not file_info: raise FileNotFoundError("File not found.")
        if file_info["owner_id"] != user_ctx["user_id"] and user_ctx["role"] != "admin":
            raise PermissionError("Access violation.")

        plan_chunks, node_count = [], len(self.storage_nodes)
        for c in self.db.get_chunks_by_file_id(file_info["id"]):
            idx = c["chunk_index"]
            n1 = self.storage_nodes[idx % node_count]
            n2 = self.storage_nodes[(idx + 1) % node_count]
            n3 = self.storage_nodes[(idx + 2) % node_count]

            plan_chunks.append({
                "index": idx, "chunk_filename": c["chunk_filename"], "size": c["size"],
                "nodes": [
                    {"node_id": n1["node_id"], "client_host": n1["client_host"], "tcp_port": n1["client_tcp_port"]},
                    {"node_id": n2["node_id"], "client_host": n2["client_host"], "tcp_port": n2["client_tcp_port"]},
                    {"node_id": n3["node_id"], "client_host": n3["client_host"], "tcp_port": n3["client_tcp_port"]}
                ]
            })
        return {"file_id": file_info["id"], "filename": filename, "size": file_info["size"], "chunks": plan_chunks}

    def commit_file_chunks(self, file_id: int, chunks: list):
        for chunk in chunks:
            self.db.add_chunk(file_id, chunk["index"], chunk["node_id"], chunk["chunk_filename"], chunk["size"])

    def get_file_deletion_plan(self, file_id: int) -> list:
        targets, node_count = [], len(self.storage_nodes)
        for c in self.db.get_chunks_by_file_id(file_id):
            idx = c["chunk_index"]
            pipeline_nodes = [
                self.storage_nodes[idx % node_count],
                self.storage_nodes[(idx + 1) % node_count],
                self.storage_nodes[(idx + 2) % node_count]
            ]
            for node in pipeline_nodes:
                targets.append({
                    "chunk_filename": c["chunk_filename"],
                    "client_host": node["client_host"],
                    "tcp_port": node["client_tcp_port"]
                })
        return targets

