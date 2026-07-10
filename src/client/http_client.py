"""HTTP Client component for interacting with the AdriaBOX Metadata Server."""
import requests
from client.exceptions import BackendServerError

class AdriaHTTPClient:
    def __init__(self, metadata_url: str, request_timeout: float):
        self.metadata_url = metadata_url
        self.request_timeout = request_timeout
        self.session = requests.Session()

    def _unwrap_response(self, response: requests.Response, return_json=True):
        """Intercept response state. If an error code is hit, extract the server JSON message."""
        if not response.ok:
            try:
                # Attempt to extract the custom server-side error message
                server_error = response.json().get("error")
                if server_error:
                    raise BackendServerError(server_error)
            except (ValueError, requests.exceptions.JSONDecodeError):
                # Fallback if the server didn't return valid JSON error metadata
                pass
            response.raise_for_status()
            
        return response.json() if return_json else response

    def update_auth_header(self, token: str):
        """Sync the HTTP headers with the active JWT session token."""
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            self.session.headers.pop("Authorization", None)

    def register(self, username, password) -> dict:
        r = self.session.post(f"{self.metadata_url}/register", json={"username": username, "password": password}, timeout=self.request_timeout)
        return self._unwrap_response(r)

    def login(self, username, password) -> dict:
        r = self.session.post(f"{self.metadata_url}/login", json={"username": username, "password": password}, timeout=self.request_timeout)
        return self._unwrap_response(r)

    def get_upload_plan(self, filename: str, size: int, remote_dir: str) -> dict:
        r = self.session.post(f"{self.metadata_url}/files/upload-plan", json={"filename": filename, "size": size, "remote_dir": remote_dir}, timeout=self.request_timeout)
        return self._unwrap_response(r)

    def complete_upload(self, file_id: int, remote_path: str, chunks: list, size: int) -> dict:
        payload = {"file_id": file_id, "remote_path": remote_path, "chunks": chunks, "size": size}
        r = self.session.post(f"{self.metadata_url}/files/complete", json=payload, timeout=self.request_timeout)
        return self._unwrap_response(r)

    def get_download_plan(self, filename: str) -> dict:
        r = self.session.get(f"{self.metadata_url}/files/download-plan", params={"filename": filename}, timeout=self.request_timeout)
        return self._unwrap_response(r)

    def list_files(self, directory_path: str) -> list:
        r = self.session.get(f"{self.metadata_url}/files/list", params={"directory": directory_path}, timeout=self.request_timeout)
        return self._unwrap_response(r).get("files", [])

    def remove_file_metadata(self, filename: str) -> dict:
        r = self.session.delete(f"{self.metadata_url}/files/remove", params={"filename": filename}, timeout=self.request_timeout)
        return self._unwrap_response(r)

    def mkdir(self, directory_path: str) -> dict:
        r = self.session.post(f"{self.metadata_url}/files/mkdir", json={"path": directory_path}, timeout=self.request_timeout)
        return self._unwrap_response(r)

    def rmdir_metadata(self, directory_path: str) -> dict:
        r = self.session.delete(f"{self.metadata_url}/files/rmdir", params={"path": directory_path}, timeout=self.request_timeout)
        return self._unwrap_response(r)

    def mv_metadata(self, source: str, destination: str) -> requests.Response:
        r = self.session.post(f"{self.metadata_url}/files/move", json={"source": source, "destination": destination}, timeout=self.request_timeout)
        return self._unwrap_response(r, return_json=False)

    def get_quota(self) -> int:
        r = self.session.get(f"{self.metadata_url}/files/quota", timeout=self.request_timeout)
        return self._unwrap_response(r).get("total_bytes", 0)

    def cluster_status(self) -> dict:
        r = self.session.get(f"{self.metadata_url}/cluster-status", timeout=self.request_timeout)
        return self._unwrap_response(r)

    def admin_list_users(self) -> requests.Response:
        r = self.session.get(f"{self.metadata_url}/admin/users", timeout=self.request_timeout)
        return self._unwrap_response(r, return_json=False)

    def admin_delete_user_metadata(self, target_username, admin_password) -> dict:
        payload = {"target_username": target_username, "admin_password": admin_password}
        r = self.session.post(f"{self.metadata_url}/admin/userdel", json=payload, timeout=self.request_timeout)
        return self._unwrap_response(r)
