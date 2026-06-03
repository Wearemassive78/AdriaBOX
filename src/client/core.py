"""Facade interface unifying HTTP metadata routing and TCP transport streams."""
import os
import requests
from client.session import SessionManager
from client.crypto import CryptoManager
from client.http_client import AdriaHTTPClient
from client.transfer import AdriaTransferManager

class AdriaClient:
    def __init__(self, metadata_url="http://localhost:5000", request_timeout=10.0):
        self.session_manager = SessionManager()
        self.http = AdriaHTTPClient(metadata_url, request_timeout)
        self.transfer = AdriaTransferManager(request_timeout)
        
        session_data = self.session_manager.load_session()
        if session_data and "token" in session_data:
            self.auth_token = session_data["token"]
            self.current_username = session_data.get("username")
            self.crypto_key = session_data.get("crypto_key")
            self.http.update_auth_header(self.auth_token)
        else:
            self.auth_token = self.current_username = self.crypto_key = None

    def register(self, username, password) -> dict:
        return self.http.register(username, password)

    def login(self, username, password) -> dict:
        data = self.http.login(username, password)
        self.auth_token, self.current_username = data["token"], data["username"]
        self.crypto_key = CryptoManager.derive_key(password, self.current_username)
        
        self.http.update_auth_header(self.auth_token)
        self.session_manager.save_session(self.auth_token, self.current_username, self.crypto_key)
        return data

    def logout(self):
        self.session_manager.clear_session()
        self.auth_token = self.current_username = self.crypto_key = None
        self.http.update_auth_header(None)

    def upload(self, local_filepath, remote_dir="/") -> dict:
        if not self.auth_token or not self.crypto_key: raise Exception("Authentication and encryption key required.")
        file_size, filename = os.path.getsize(local_filepath), os.path.basename(local_filepath)

        plan = self.http.get_upload_plan(filename, file_size, remote_dir)
        if "error" in plan: raise Exception(f"Upload plan rejected by Master: {plan['error']}")

        uploaded_chunks = self.transfer.upload_file_chunks(local_filepath, plan.get("chunks", []), self.crypto_key)
        return self.http.complete_upload(plan["file_id"], plan["remote_path"], uploaded_chunks, file_size)

    def download(self, filename, local_destination=None) -> str:
        if not self.auth_token or not self.crypto_key: raise Exception("Authentication and encryption key required.")
        local_destination = local_destination or os.path.join(os.getcwd(), os.path.basename(filename))

        plan = self.http.get_download_plan(filename)
        if "error" in plan: raise Exception(f"Download rejected by Master: {plan['error']}")

        self.transfer.download_file_chunks(local_destination, plan.get("chunks", []), self.crypto_key)
        return local_destination

    def list_files(self, directory_path="/") -> list:
        if not self.auth_token: raise Exception("Authentication required.")
        return self.http.list_files(directory_path)

    def rm(self, filename) -> bool:
        if not self.auth_token: raise Exception("Authentication required.")
        plan = self.http.remove_file_metadata(filename)
        self.transfer.purge_physical_chunks(plan.get("chunks", []))
        return True

    def mkdir(self, directory_path) -> dict:
        if not self.auth_token: raise Exception("Authentication required.")
        return self.http.mkdir(directory_path)

    def rmdir(self, directory_path) -> bool:
        if not self.auth_token: raise Exception("Authentication required.")
        response = self.http.rmdir_metadata(directory_path)
        
        try:
            response.raise_for_status()
            plan = response.json()
        except requests.exceptions.HTTPError as e:
            try: error_msg = response.json().get("error", str(e))
            except Exception: error_msg = f"Server returned {response.status_code}."
            raise Exception(f"Failed to remove directory: {error_msg}")

        self.transfer.purge_physical_chunks(plan.get("chunks", []))
        return True

    def mv(self, source, destination) -> dict:
        if not self.auth_token: raise Exception("Authentication required.")
        response = self.http.mv_metadata(source, destination)
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try: error_msg = response.json().get("error", str(e))
            except Exception: error_msg = f"Server returned {response.status_code}"
            raise Exception(f"Failed to move: {error_msg}")

    def get_quota(self) -> int:
        if not self.auth_token: raise Exception("Authentication required.")
        return self.http.get_quota()

    def cluster_status(self) -> dict:
        if not self.auth_token: raise Exception("Authentication required.")
        return self.http.cluster_status()

    def admin_list_users(self) -> list:
        if not self.auth_token: raise Exception("Authentication required.")
        response = self.http.admin_list_users()
        try:
            response.raise_for_status()
            return response.json().get("users", [])
        except requests.exceptions.HTTPError as e:
            try: error_msg = response.json().get("error", str(e))
            except Exception: error_msg = f"Server returned {response.status_code}"
            raise Exception(f"Admin action failed: {error_msg}")

    def admin_delete_user(self, target_username, admin_password) -> dict:
        if not self.auth_token: raise Exception("Authentication required.")
        response = self.http.admin_delete_user_metadata(target_username, admin_password)
        try:
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.HTTPError as e:
            try: error_msg = response.json().get("error", str(e))
            except Exception: error_msg = f"Server returned {response.status_code}"
            raise Exception(f"Admin action failed: {error_msg}")

        self.transfer.purge_physical_chunks(result.get("chunks", []))
        return result

