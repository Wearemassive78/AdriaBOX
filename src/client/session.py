"""Local session management for AdriaBOX client."""
import json
import os

class SessionManager:
    """Manages local user session, JWT token, and encryption keys."""

    def __init__(self, session_file="session.json"):
        # Store the session file safely in the data directory
        self.session_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", session_file)
        os.makedirs(os.path.dirname(self.session_file), exist_ok=True)

    def save_session(self, token, username, crypto_key=None, role=None):
        """Persists the JWT token and the local Zero-Knowledge encryption key."""
        data = {"token": token, "username": username}
        if role:
            data["role"] = role
        if crypto_key:
            data["crypto_key"] = crypto_key
            
        with open(self.session_file, "w") as f:
            json.dump(data, f)

    def load_session(self):
        """Retrieves the active session data."""
        if not os.path.exists(self.session_file):
            return None
        try:
            with open(self.session_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None

    def clear_session(self):
        """Destroys the local session, including the encryption key."""
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
