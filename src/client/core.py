import os
import requests
import json
from client.session import SessionManager
from client.crypto import CryptoManager

class AdriaClient:
    """
    Core client logic for AdriaBOX.
    Handles communication with the Metadata Server and coordinates storage nodes.
    """

    def __init__(self, metadata_url="http://localhost:5000", request_timeout=10.0):
        self.metadata_url = metadata_url
        self.request_timeout = request_timeout
        self.session_manager = SessionManager()
        self.session = requests.Session()
        
        # Load existing session if available
        session_data = self.session_manager.load_session()
        if session_data and "token" in session_data:
            self.auth_token = session_data["token"]
            self.current_username = session_data.get("username")
            self.current_role = session_data.get("role", "user")
            self.crypto_key = session_data.get("crypto_key")
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        else:
            self.auth_token = None
            self.current_username = None
            self.current_role = None
            self.crypto_key = None

    def register(self, username, password):
        """Registers a new user on the metadata server."""
        response = self.session.post(
            f"{self.metadata_url}/register",
            json={"username": username, "password": password},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        return response.json()

    def login(self, username, password):
        """Authenticates the user, starts session, and derives Zero-Knowledge key."""
        response = self.session.post(
            f"{self.metadata_url}/login",
            json={"username": username, "password": password},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        self.auth_token = data["token"]
        self.current_username = data["username"]
        self.current_role = data.get("role", "user")
        
        # NEW: Derive the local AES-256 encryption key (Never leaves this PC!)
        self.crypto_key = CryptoManager.derive_key(password, self.current_username)
        
        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        
        # Save session including the local crypto key
        self.session_manager.save_session(self.auth_token, self.current_username, self.crypto_key, self.current_role)
        return data

    def logout(self):
        """Clears the local session, headers, and destroys the crypto key in RAM."""
        self.session_manager.clear_session()
        self.auth_token = None
        self.current_username = None
        self.current_role = None
        self.crypto_key = None
        self.session.headers.pop("Authorization", None)

    def upload(self, local_filepath, remote_dir="/"):
        if not self.auth_token:
            raise Exception("Authentication required. Please login first.")
        if not self.crypto_key:
            raise Exception("Missing encryption key. Please login again.")

        file_size = os.path.getsize(local_filepath)
        filename = os.path.basename(local_filepath)

        plan_response = self.session.post(
            f"{self.metadata_url}/files/upload-plan",
            json={"filename": filename, "size": file_size, "remote_dir": remote_dir},
            timeout=self.request_timeout,
        )
        plan_response.raise_for_status()
        plan = plan_response.json()

        from common.tcp import ChunkStreamSender
        uploaded_chunks = []

        with open(local_filepath, "rb") as source:
            for chunk in plan.get("chunks", []):
                source.seek(chunk["offset"])
                
                # Pass the crypto_key to the network layer
                sender = ChunkStreamSender(
                    chunk["client_host"],
                    int(chunk["tcp_port"]),
                    timeout=self.request_timeout,
                    crypto_key=self.crypto_key
                )
                
                chunk_hash = sender.send(source, chunk["chunk_filename"], chunk["size"])
                
                uploaded_chunks.append({
                    "index": chunk["index"],
                    "chunk_filename": chunk["chunk_filename"],
                    "node_id": chunk["node_id"],
                    "size": chunk["size"],
                    "sha256": chunk_hash
                })

        complete_response = self.session.post(
            f"{self.metadata_url}/files/complete",
            json={
                "file_id": plan["file_id"],
                "filename": filename,
                "chunks": uploaded_chunks,
                "size": file_size
            },
            timeout=self.request_timeout,
        )
        complete_response.raise_for_status()
        return complete_response.json()

    def download(self, filename, local_destination=None):
        if not self.auth_token:
            raise Exception("Authentication required. Please login first.")
        if not self.crypto_key:
            raise Exception("Missing encryption key. Please login again.")

        if not local_destination:
            local_destination = os.path.join(os.getcwd(), filename)

        from common.tcp import ChunkDownloader

        plan_response = self.session.get(
            f"{self.metadata_url}/files/download-plan",
            params={"filename": filename},
            timeout=self.request_timeout,
        )
        plan_response.raise_for_status()
        plan = plan_response.json()

        with open(local_destination, "wb") as dest_file:
            for chunk in plan.get("chunks", []):
                # Pass the crypto_key to the network layer
                downloader = ChunkDownloader(
                    chunk["client_host"],
                    int(chunk["tcp_port"]),
                    timeout=self.request_timeout,
                    crypto_key=self.crypto_key
                )
                downloader.download(chunk["chunk_filename"], dest_file, chunk["size"])

        return local_destination

    def list_files(self):
        """
        Requests the list of owned files from the metadata server.
        """
        if not self.auth_token:
            raise Exception("Authentication required. Please login first.")

        response = self.session.get(
            f"{self.metadata_url}/files/list",
            timeout=self.request_timeout
        )
        response.raise_for_status()
        return response.json().get("files", [])

    def rm(self, filename):
        """
        Deletes a file from the cluster (both metadata and physical chunks).
        """
        if not self.auth_token:
            raise Exception("Authentication required. Please login first.")

        # 1. Ask Master to delete metadata and give us the chunk locations
        response = self.session.delete(
            f"{self.metadata_url}/files/remove",
            params={"filename": filename},
            timeout=self.request_timeout
        )
        response.raise_for_status()
        plan = response.json()

        from common.tcp import ChunkDeleter

        # 2. Connect to nodes and physically delete the chunks
        for chunk in plan.get("chunks", []):
            try:
                deleter = ChunkDeleter(
                    chunk["client_host"],
                    int(chunk["tcp_port"]),
                    timeout=self.request_timeout
                )
                deleter.delete(chunk["chunk_filename"])
            except Exception as e:
                # We catch errors here so one down node doesn't break the whole loop
                print(f"Warning: Could not delete chunk {chunk['chunk_filename']} from node: {e}")

        return True
