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
        """Transform the raw environment string into a structured network topology matrix."""
        if not cfg_string:
            return []
        nodes = []
        for item in cfg_string.split(","):
            parts = item.split(":")
            if len(parts) == 5:
                nodes.append({
                    "node_id": parts[0], "host": parts[1], "tcp_port": int(parts[2]),
                    "client_host": parts[3], "client_tcp_port": int(parts[4])
                })
        return nodes

    def generate_token(self, user_dict: dict) -> str:
        """Provision a cryptographically signed stateful JWT token from verified database records."""
        payload = {
            "user_id": user_dict["id"], 
            "username": user_dict["username"], 
            "role": user_dict["role"],
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    def authorize_request(self, auth_header: str) -> dict:
        """Intercept and decode incoming bearer authentication tokens."""
        if not auth_header or not auth_header.startswith("Bearer "):
            raise PermissionError("Missing or malformed Authorization header.")
        token = auth_header.split(" ")[1]
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise PermissionError("Session token expired.")
        except jwt.InvalidTokenError:
            raise PermissionError("Cryptographic token corruption detected.")

    def build_upload_plan(self, user_ctx: dict, filename: str, file_size: int, remote_dir: str) -> dict:
        """Execute Chained Round-Robin matrix routing to generate a 3-node replication pipeline."""
        if len(self.storage_nodes) < 3:
            raise RuntimeError("Cluster isolation hazard: At least 3 active nodes required for replication.")

        full_path = os.path.join(remote_dir, filename).replace("\\", "/")
        if not full_path.startswith("/"): 
            full_path = "/" + full_path

        chunk_count = 1 if file_size == 0 else max(1, math.ceil(file_size / LOGICAL_BLOCK_SIZE))
        
        # Invokes your native db.add_file method
        file_id = self.db.add_file(full_path, file_size, chunk_count, owner_id=user_ctx["user_id"])

        chunks, offset = [], 0
        node_count = len(self.storage_nodes)

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
        """Reconstruct the exact deterministic replica priority list for client-side failover."""
        if not filename.startswith("/"): 
            filename = "/" + filename

        # Invokes your native db.get_file_by_name method
        file_info = self.db.get_file_by_name(filename)
        if not file_info:
            raise FileNotFoundError("Target object reference missing from ledger.")
            
        if file_info["owner_id"] != user_ctx["user_id"] and user_ctx["role"] != "admin":
            raise PermissionError("Access violation: Tenant scope cross-contamination rejected.")

        plan_chunks = []
        node_count = len(self.storage_nodes)

        # Invokes your native db.get_chunks_by_file_id method
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
        """Persist chunk transactional positioning inside the relational metadata ledger."""
        for chunk in chunks:
            # Invokes your native db.save_chunk_metadata method
            self.db.save_chunk_metadata(
                file_id=file_id, chunk_index=chunk["index"],
                node_id=chunk["node_id"], chunk_filename=chunk["chunk_filename"],
                size=chunk["size"]
            )

