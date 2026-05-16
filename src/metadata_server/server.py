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
    raw_nodes = os.environ.get("ADRIABOX_STORAGE_NODES")
    if raw_nodes:
        nodes = []
        for index, item in enumerate(raw_nodes.split(","), start=1):
            parts = item.split(":")
            if len(parts) != 5:
                raise ValueError("ADRIABOX_STORAGE_NODES items must be node_id:host:tcp_port:client_host:client_tcp_port")
            node_id, host, tcp_port, client_host, client_tcp_port = parts
            nodes.append({
                "node_id": node_id, "host": host, "tcp_port": int(tcp_port),
                "client_host": client_host, "client_tcp_port": int(client_tcp_port),
            })
        return nodes

    return [
        {"node_id": "storage1", "host": "storage1", "tcp_port": 7001, "client_host": "127.0.0.1", "client_tcp_port": 7001},
        {"node_id": "storage2", "host": "storage2", "tcp_port": 7002, "client_host": "127.0.0.1", "client_tcp_port": 7002},
        {"node_id": "storage3", "host": "storage3", "tcp_port": 7003, "client_host": "127.0.0.1", "client_tcp_port": 7003},
    ]

class AdriaServer:

    def __init__(self, db_path=DEFAULT_DB_PATH, secret_key="super-secret-master-key-for-adriabox"):
        self.app = Flask(__name__)
        self.db = DatabaseManager(db_path)
        self.secret_key = secret_key
        self.storage_nodes = load_storage_nodes()

        self.app.add_url_rule("/health", view_func=self.health, methods=["GET"])
        self.app.add_url_rule("/register", view_func=self.register, methods=["POST"])
        self.app.add_url_rule("/login", view_func=self.login, methods=["POST"])
        
        # Filesystem Endpoints
        self.app.add_url_rule("/files/upload-plan", view_func=self.create_upload_plan, methods=["POST"])
        self.app.add_url_rule("/files/complete", view_func=self.complete_upload, methods=["POST"])
        self.app.add_url_rule("/files/download-plan", view_func=self.create_download_plan, methods=["GET"])
        self.app.add_url_rule("/files/list", view_func=self.list_files, methods=["GET"])
        self.app.add_url_rule("/files/remove", view_func=self.remove_file, methods=["DELETE"])
        self.app.add_url_rule("/files/quota", view_func=self.get_quota, methods=["GET"])
        
        # Directory specific endpoints (S3 Philosophy)
        self.app.add_url_rule("/files/mkdir", view_func=self.make_directory, methods=["POST"])
        self.app.add_url_rule("/files/rmdir", view_func=self.remove_directory, methods=["DELETE"])
        self.app.add_url_rule("/files/move", view_func=self.move_item, methods=["POST"])

    def _get_current_user(self):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "): return None
        try:
            return jwt.decode(auth_header.split(" ")[1], self.secret_key, algorithms=["HS256"])
        except Exception:
            return None

    def health(self):
        return jsonify({"status": "ok", "nodes": self.storage_nodes})

    def register(self):
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")
        if not username or not password: return jsonify({"error": "Missing credentials"}), 400
        try:
            self.db.register_user(username, password)
            return jsonify({"message": "User registered"}), 201
        except ValueError:
            return jsonify({"error": "Username already exists"}), 409

    def login(self):
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")
        if not username or not password: return jsonify({"error": "Missing credentials"}), 400

        user = self.db.verify_user(username, password)
        if not user: return jsonify({"error": "Invalid credentials"}), 401

        payload = {
            "user_id": user["id"], "username": user["username"], "role": user.get("role", "user"),
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        }
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        if isinstance(token, bytes): token = token.decode("utf-8")
        return jsonify({"token": token, "username": user["username"], "role": user.get("role", "user")}), 200

    def create_upload_plan(self):
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401

        data = request.json or {}
        filename = data.get("filename")
        file_size = int(data.get("size") or 0)
        remote_dir = data.get("remote_dir") or "/"

        if not filename: return jsonify({"error": "Missing filename"}), 400
        
        # S3 Philosophy: We store the absolute path as the filename
        full_path = os.path.join(remote_dir, filename).replace("\\", "/")
        if not full_path.startswith("/"): full_path = "/" + full_path

        chunk_count = 1 if file_size == 0 else max(1, math.ceil(file_size / LOGICAL_BLOCK_SIZE))
        file_id = self.db.add_file(full_path, file_size, chunk_count, owner_id=current_user["user_id"])

        chunks, offset, node_count = [], 0, len(self.storage_nodes)
        for index in range(chunk_count):
            node = self.storage_nodes[index % node_count]
            size = min(LOGICAL_BLOCK_SIZE, file_size - offset)
            if size <= 0 and index == 0: size = 0
                
            chunk_filename = f"{file_id}_{index}_{os.path.basename(filename)}.chunk"
            chunks.append({
                "index": index, "offset": offset, "size": size, "chunk_filename": chunk_filename,
                "node_id": node["node_id"], "host": node["host"], "tcp_port": node["client_tcp_port"],
                "client_host": node["client_host"],
            })
            offset += size

        return jsonify({"file_id": file_id, "filename": full_path, "remote_path": full_path, "size": file_size, "chunks": chunks}), 200

    def create_download_plan(self):
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401

        filename = request.args.get("filename")
        if not filename: return jsonify({"error": "Missing filename"}), 400

        # Enforce absolute path searching
        if not filename.startswith("/"): filename = "/" + filename

        file_info = self.db.get_file_by_name(filename)
        if not file_info: return jsonify({"error": "File not found"}), 404
        if file_info["owner_id"] != current_user["user_id"] and current_user["role"] != "admin": return jsonify({"error": "Forbidden"}), 403

        plan_chunks = []
        for c in self.db.get_chunks_by_file_id(file_info["id"]):
            node_cfg = next((n for n in self.storage_nodes if n["node_id"] == c["node_id"]), self.storage_nodes[0])
            plan_chunks.append({
                "index": c["chunk_index"], "chunk_filename": c["chunk_filename"], "size": c["size"],
                "node_id": c["node_id"], "client_host": node_cfg["client_host"], "tcp_port": node_cfg["client_tcp_port"]
            })

        return jsonify({"file_id": file_info["id"], "filename": filename, "size": file_info["size"], "chunks": plan_chunks}), 200

    def complete_upload(self):
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401
        data = request.json or {}
        
        for chunk in data.get("chunks", []):
            self.db.save_chunk_metadata(
                file_id=data["file_id"], chunk_index=chunk["index"], node_id=chunk["node_id"],
                chunk_filename=chunk["chunk_filename"], size=chunk["size"]
            )
            
        # FIXED: Return the full chunk list and path so the CLI can print the table
        return jsonify({
            "message": "Upload completed",
            "remote_path": data.get("remote_path"),
            "chunks": data.get("chunks", [])
        }), 200

    def list_files(self):
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401

        directory = request.args.get("directory", "/")
        if not directory.endswith("/"): directory += "/"
        if not directory.startswith("/"): directory = "/" + directory

        all_files = self.db.get_user_files(current_user["user_id"])
        results = {}
        
        for f in all_files:
            # Gracefully handle old files uploaded before we enforced absolute paths
            path = f["filename"]
            if not path.startswith("/"): path = "/" + path

            if path.startswith(directory):
                relative_path = path[len(directory):]
                if "/" in relative_path:
                    folder_name = relative_path.split("/")[0] + "/"
                    if folder_name not in results:
                        results[folder_name] = {"filename": folder_name, "size": 0, "chunks": 0, "created_at": "-", "is_dir": True}
                else:
                    if relative_path: # Ignore the 0-byte directory placeholder itself
                        f["filename"] = relative_path
                        f["is_dir"] = False
                        results[relative_path] = f

        return jsonify({"files": list(results.values())}), 200

    def make_directory(self):
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401

        path = (request.json or {}).get("path")
        if not path: return jsonify({"error": "Missing path"}), 400

        # Enforce folder naming convention
        if not path.startswith("/"): path = "/" + path
        if not path.endswith("/"): path += "/"

        # Create a 0-byte placeholder to simulate a folder
        self.db.add_file(path, 0, 0, owner_id=current_user["user_id"])
        return jsonify({"message": "Directory created"}), 201

    def remove_file(self):
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401

        filename = request.args.get("filename")
        if not filename.startswith("/"): filename = "/" + filename

        file_info = self.db.get_file_by_name(filename)
        if not file_info: return jsonify({"error": "File not found"}), 404
        if file_info["owner_id"] != current_user["user_id"]: return jsonify({"error": "Forbidden"}), 403

        plan_chunks = []
        for c in self.db.get_chunks_by_file_id(file_info["id"]):
            node_cfg = next((n for n in self.storage_nodes if n["node_id"] == c["node_id"]), self.storage_nodes[0])
            plan_chunks.append({"chunk_filename": c["chunk_filename"], "client_host": node_cfg["client_host"], "tcp_port": node_cfg["client_tcp_port"]})

        self.db.delete_file(file_info["id"])
        return jsonify({"message": "Metadata deleted successfully", "chunks": plan_chunks}), 200

    def remove_directory(self):
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401

        directory = request.args.get("path")
        if not directory.startswith("/"): directory = "/" + directory
        if not directory.endswith("/"): directory += "/"

        all_files = self.db.get_user_files(current_user["user_id"])
        chunks_to_delete, files_deleted = [], 0
        
        for f in all_files:
            path = f.get("filename", "")
            if not path.startswith("/"): path = "/" + path
            if path.startswith(directory):
                file_id = f.get("id") or f.get("file_id")

                if not file_id:
                    db_record = self.db.get_file_by_name(path)
                    if db_record:
                        file_id = db_record.get("id") or db_record.get("file_id")
                        
                if not file_id:
                    continue
                    
                for c in self.db.get_chunks_by_file_id(file_id):
                    node_cfg = next((n for n in self.storage_nodes if n["node_id"] == c["node_id"]), self.storage_nodes[0])
                    chunks_to_delete.append({"chunk_filename": c["chunk_filename"], "client_host": node_cfg["client_host"], "tcp_port": node_cfg["client_tcp_port"]})
                
                self.db.delete_file(file_id)
                files_deleted += 1

        if files_deleted == 0: return jsonify({"error": "Directory not found or empty"}), 404
        return jsonify({"message": f"Deleted {files_deleted} items in directory", "chunks": chunks_to_delete}), 200

    def move_item(self):
        """
        Moves or renames a file or an entire directory by updating prefixes.
        """
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401

        data = request.json or {}
        source = data.get("source")
        destination = data.get("destination")
        
        if not source or not destination: 
            return jsonify({"error": "Missing source or destination"}), 400

        # Normalize absolute paths
        if not source.startswith("/"): source = "/" + source
        if not destination.startswith("/"): destination = "/" + destination

        exact_file = self.db.get_file_by_name(source)
        moved_count = 0

        # Scenario A: Moving a single specific file
        if exact_file and not source.endswith("/"):
            if exact_file["owner_id"] != current_user["user_id"]:
                return jsonify({"error": "Forbidden"}), 403

            # --- NUOVO: Controllo intelligente (Stile Linux) ---
            # Se manca la barra finale, ma esiste già una directory con quel nome,
            # la aggiungiamo noi automaticamente.
            if not destination.endswith("/") and self.db.get_file_by_name(destination + "/"):
                destination += "/"

            # If destination is a folder (ends with /), put the file inside it
            if destination.endswith("/"):
                destination = destination + os.path.basename(source)
            
            if self.db.get_file_by_name(destination):
                return jsonify({"error": "Destination file already exists"}), 409
                
            self.db.rename_file(exact_file["id"], destination)
            moved_count = 1

        # Scenario B: Moving an entire directory
        else:
            src_dir = source if source.endswith("/") else source + "/"
            dest_dir = destination if destination.endswith("/") else destination + "/"
            
            all_files = self.db.get_user_files(current_user["user_id"])
            files_to_move = [f for f in all_files if f.get("filename", "").startswith(src_dir)]
            
            if not files_to_move:
                return jsonify({"error": "Source not found or empty"}), 404
                
            for f in files_to_move:
                path = f.get("filename", "")
                if not path.startswith("/"): path = "/" + path
                
                # Estrazione robusta dell'ID (come in rmdir)
                file_id = f.get("id") or f.get("file_id")
                if not file_id:
                    db_record = self.db.get_file_by_name(path)
                    if db_record:
                        file_id = db_record.get("id") or db_record.get("file_id")
                        
                if not file_id:
                    continue # Salta se la riga è illeggibile
                    
                # Calcola il nuovo percorso sostituendo il prefisso S3
                new_path = dest_dir + path[len(src_dir):]
                self.db.rename_file(file_id, new_path)
                moved_count += 1
        
        return jsonify({"message": f"Successfully moved {moved_count} items."}), 200

    def get_quota(self):
        current_user = self._get_current_user()
        if not current_user: return jsonify({"error": "Unauthorized"}), 401
        return jsonify({"username": current_user["username"], "total_bytes": self.db.get_user_quota(current_user["user_id"])}), 200

    def run(self, host="0.0.0.0", port=5000):
        self.app.run(host=host, port=port, debug=True)

if __name__ == "__main__":
    server = AdriaServer()
    server.run()
