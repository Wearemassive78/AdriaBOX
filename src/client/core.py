import os
import requests
import json
from client.session import SessionManager
from client.crypto import CryptoManager

class AdriaClient:

    def __init__(self, metadata_url="http://localhost:5000", request_timeout=10.0):
        self.metadata_url = metadata_url
        self.request_timeout = request_timeout
        self.session_manager = SessionManager()
        self.session = requests.Session()
        
        session_data = self.session_manager.load_session()
        if session_data and "token" in session_data:
            self.auth_token, self.current_username, self.crypto_key = session_data["token"], session_data.get("username"), session_data.get("crypto_key")
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        else:
            self.auth_token = self.current_username = self.crypto_key = None

    def register(self, username, password):
        response = self.session.post(f"{self.metadata_url}/register", json={"username": username, "password": password}, timeout=self.request_timeout)
        response.raise_for_status()
        return response.json()

    def login(self, username, password):
        response = self.session.post(f"{self.metadata_url}/login", json={"username": username, "password": password}, timeout=self.request_timeout)
        response.raise_for_status()
        data = response.json()
        
        self.auth_token, self.current_username = data["token"], data["username"]
        self.crypto_key = CryptoManager.derive_key(password, self.current_username)
        
        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        self.session_manager.save_session(self.auth_token, self.current_username, self.crypto_key)
        return data

    def logout(self):
        self.session_manager.clear_session()
        self.auth_token = self.current_username = self.crypto_key = None
        self.session.headers.pop("Authorization", None)

    def upload(self, local_filepath, remote_dir="/"):
        if not self.auth_token: raise Exception("Authentication required.")
        if not self.crypto_key: raise Exception("Missing encryption key.")

        file_size, filename = os.path.getsize(local_filepath), os.path.basename(local_filepath)

        plan = self.session.post(f"{self.metadata_url}/files/upload-plan", json={"filename": filename, "size": file_size, "remote_dir": remote_dir}, timeout=self.request_timeout).json()

        from common.tcp import ChunkStreamSender
        uploaded_chunks = []
        with open(local_filepath, "rb") as source:
            for chunk in plan.get("chunks", []):
                source.seek(chunk["offset"])
                sender = ChunkStreamSender(chunk["client_host"], int(chunk["tcp_port"]), timeout=self.request_timeout, crypto_key=self.crypto_key)
                uploaded_chunks.append({
                    "index": chunk["index"], "chunk_filename": chunk["chunk_filename"], "node_id": chunk["node_id"],
                    "size": chunk["size"], "sha256": sender.send(source, chunk["chunk_filename"], chunk["size"])
                })

        return self.session.post(f"{self.metadata_url}/files/complete", json={"file_id": plan["file_id"], "remote_path": plan["remote_path"], "chunks": uploaded_chunks, "size": file_size}, timeout=self.request_timeout).json()

    def download(self, filename, local_destination=None):
        if not self.auth_token or not self.crypto_key: raise Exception("Authentication and encryption key required.")
        local_destination = local_destination or os.path.join(os.getcwd(), os.path.basename(filename))

        plan = self.session.get(f"{self.metadata_url}/files/download-plan", params={"filename": filename}, timeout=self.request_timeout).json()

        from common.tcp import ChunkDownloader
        with open(local_destination, "wb") as dest_file:
            for chunk in plan.get("chunks", []):
                downloader = ChunkDownloader(chunk["client_host"], int(chunk["tcp_port"]), timeout=self.request_timeout, crypto_key=self.crypto_key)
                downloader.download(chunk["chunk_filename"], dest_file, chunk["size"])
        return local_destination

    def list_files(self, directory_path="/"):
        if not self.auth_token: raise Exception("Authentication required.")
        return self.session.get(f"{self.metadata_url}/files/list", params={"directory": directory_path}, timeout=self.request_timeout).json().get("files", [])

    def rm(self, filename):
        if not self.auth_token: raise Exception("Authentication required.")
        plan = self.session.delete(f"{self.metadata_url}/files/remove", params={"filename": filename}, timeout=self.request_timeout).json()

        from common.tcp import ChunkDeleter
        for chunk in plan.get("chunks", []):
            try: ChunkDeleter(chunk["client_host"], int(chunk["tcp_port"]), timeout=self.request_timeout).delete(chunk["chunk_filename"])
            except Exception: pass
        return True

    def mkdir(self, directory_path):
        if not self.auth_token: raise Exception("Authentication required.")
        response = self.session.post(f"{self.metadata_url}/files/mkdir", json={"path": directory_path}, timeout=self.request_timeout)
        response.raise_for_status()
        return response.json()

    def rmdir(self, directory_path):
        if not self.auth_token: raise Exception("Authentication required.")
        
        response = self.session.delete(f"{self.metadata_url}/files/rmdir", params={"path": directory_path}, timeout=self.request_timeout)
        
        # Safe JSON parsing to prevent "Expecting value" HTML crashes
        try:
            response.raise_for_status()
            plan = response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_msg = response.json().get("error", str(e))
            except Exception:
                error_msg = f"Server returned {response.status_code}. It might be offline or broken."
            raise Exception(f"Failed to remove directory: {error_msg}")

        from common.tcp import ChunkDeleter
        for chunk in plan.get("chunks", []):
            try: ChunkDeleter(chunk["client_host"], int(chunk["tcp_port"]), timeout=self.request_timeout).delete(chunk["chunk_filename"])
            except Exception: pass
        return True

    def mv(self, source, destination):
        """
        Moves or renames a remote file or directory.
        """
        if not self.auth_token: raise Exception("Authentication required.")
        
        response = self.session.post(
            f"{self.metadata_url}/files/move", 
            json={"source": source, "destination": destination}, 
            timeout=self.request_timeout
        )
        
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try: error_msg = response.json().get("error", str(e))
            except Exception: error_msg = f"Server returned {response.status_code}"
            raise Exception(f"Failed to move: {error_msg}")

    def get_quota(self):
        if not self.auth_token: raise Exception("Authentication required.")
        return self.session.get(f"{self.metadata_url}/files/quota", timeout=self.request_timeout).json().get("total_bytes", 0)
