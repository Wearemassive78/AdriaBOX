import os
import requests

class AdriaClient:
    """Core logic for interacting with AdriaBOX cluster."""

    def __init__(self, metadata_url: str):
        """Initializes the client with the server URL and an empty token."""
        self.metadata_url = metadata_url
        self.auth_token = None
        
        # A Session object keeps the underlying TCP connection alive 
        # (connection pooling) and persists cookies/headers across requests.
        self.session = requests.Session()

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
        
        # Master returns 200 OK (Auth Token) [cite: 2]
        # Store Token locally in memory [cite: 3]
        self.auth_token = data.get("token")
        
        # Configure the HTTP session to automatically attach the Auth Token
        # to the headers of ALL future HTTP requests.
        if self.auth_token:
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        
        return data

