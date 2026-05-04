import os
import requests
import jwt
from client.session import SessionManager

class AdriaClient:
    """Core logic for interacting with AdriaBOX cluster."""

    def __init__(self, metadata_url: str):
        """Initializes the client with the server URL and an empty token."""
        self.metadata_url = metadata_url
        self.session_manager = SessionManager()
        session_data = self.session_manager.load_session() or {}
        self.auth_token = session_data.get('token')
        self.current_username = session_data.get('username')
        self.current_role = session_data.get('role')
        
        # A Session object keeps the underlying TCP connection alive 
        # (connection pooling) and persists cookies/headers across requests.
        self.session = requests.Session()

        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            # If the session file only contains a token (older clients),
            # decode the JWT payload (without verifying) to populate username/role for display.
            if not self.current_username:
                try:
                    payload = jwt.decode(self.auth_token, options={"verify_signature": False})
                    self.current_username = payload.get('username')
                    self.current_role = payload.get('role')
                except Exception:
                    # Ignore decode errors; leave username/role as None
                    pass

    def register(self, username, password):
        """
        Implements: adria register <user> <pass>
        Sends credentials to the Master node.
        """
        url = f"{self.metadata_url}/register"
        payload = {
            "username": username,
            "password": password
        }
        
        # Equivalent to an HTTP POST request 
        response = self.session.post(url, json=payload)
        
        # Checks if the server returned an HTTP error (e.g., 400 Bad Request)
        # and throws an exception if it did.
        response.raise_for_status() 
        
        # Master returns 201 Created (User registered) [cite: 1]
        return response.json()

    def login(self, username, password):
        """
        Implements: adria login <user> <pass>
        Retrieves the JWT token and stores it in the session state.
        """
        url = f"{self.metadata_url}/login"
        payload = {
            "username": username,
            "password": password
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()

        # Master returns 200 OK (Auth Token) and user info
        self.auth_token = data.get("token")
        self.current_username = data.get('username') or username
        self.current_role = data.get('role') or 'user'

        # Configure the HTTP session to automatically attach the Auth Token
        # to the headers of ALL future HTTP requests.
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            # Persist full session (token + username + role)
            self.session_manager.save_session({
                'token': self.auth_token,
                'username': self.current_username,
                'role': self.current_role
            })

        return data


    def logout(self):
        """
        Implements: adria logout
        Clears the local token and HTTP headers.
        """
        self.auth_token = None
        self.current_username = None
        self.current_role = None
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]
        
        self.session_manager.clear_session()
