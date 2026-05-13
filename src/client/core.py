import os
import requests
import json
from client.session import SessionManager

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
            # Automatically set the Authorization header for all future requests
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        else:
            self.auth_token = None
            self.current_username = None

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
        """Authenticates the user and starts a new session."""
        response = self.session.post(
            f"{self.metadata_url}/login",
            json={"username": username, "password": password},
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        self.auth_token = data["token"]
        self.current_username = data["username"]
        
        # Update session headers with the new token
        self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        
        # Persist session locally
        self.session_manager.save_session({"token": self.auth_token, "username": self.current_username})
        return data

    def logout(self):
        """Clears the local session and headers."""
        self.session_manager.clear_session()
        self.auth_token = None
        self.current_username = None
        self.session.headers.pop("Authorization", None)

    def upload(self, local_filepath, remote_dir="/"):
        """
        Uploads a file by requesting a plan and streaming chunks to nodes.
        The JWT token is automatically included in the headers.
        """
        if not self.auth_token:
            raise Exception("Authentication required. Please login first.")

        file_size = os.path.getsize(local_filepath)
        filename = os.path.basename(local_filepath)

        # 1. Get the upload plan (Master checks JWT here)
        plan_response = self.session.post(
            f"{self.metadata_url}/files/upload-plan",
            json={
                "filename": filename,
                "size": file_size,
                "remote_dir": remote_dir
            },
            timeout=self.request_timeout,
        )
        plan_response.raise_for_status()
        plan = plan_response.json()

        from common.tcp import ChunkStreamSender
        uploaded_chunks = []

        # 2. Stream chunks to storage nodes
        with open(local_filepath, "rb") as source:
            for chunk in plan.get("chunks", []):
                source.seek(chunk["offset"])
                
                sender = ChunkStreamSender(
                    chunk["client_host"],
                    int(chunk["tcp_port"]),
                    timeout=self.request_timeout,
                )
                
                # The node receives the data via raw TCP
                chunk_hash = sender.send(source, chunk["chunk_filename"], chunk["size"])
                
                uploaded_chunks.append({
                    "index": chunk["index"],
                    "chunk_filename": chunk["chunk_filename"],
                    "node_id": chunk["node_id"],
                    "size": chunk["size"],
                    "sha256": chunk_hash
                })

        # 3. Finalize the upload on the Master
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
        """
        Downloads a file by fetching the map from the Master (JWT protected).
        """
        if not self.auth_token:
            raise Exception("Authentication required. Please login first.")

        if not local_destination:
            local_destination = os.path.join(os.getcwd(), filename)

        from common.tcp import ChunkDownloader

        # 1. Request download plan
        plan_response = self.session.get(
            f"{self.metadata_url}/files/download-plan",
            params={"filename": filename},
            timeout=self.request_timeout,
        )
        plan_response.raise_for_status()
        plan = plan_response.json()

        # 2. Rebuild the file
        with open(local_destination, "wb") as dest_file:
            for chunk in plan.get("chunks", []):
                downloader = ChunkDownloader(
                    chunk["client_host"],
                    int(chunk["tcp_port"]),
                    timeout=self.request_timeout
                )
                downloader.download(chunk["chunk_filename"], dest_file, chunk["size"])

        return local_destination
