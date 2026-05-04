import os
import json

class SessionManager:
    """Handles the local persistence of the authentication token."""

    def __init__(self, filename=".adriabox_session"):
        """
        Resolves the path to the user's home directory.
        Equivalent to getting the $HOME environment variable in C.
        """
        self.filepath = os.path.join(os.path.expanduser('~'), filename)

    def save_token(self, token: str):
        """Writes the token to a hidden file on disk."""
        # The 'w' flag opens the file for writing (creates it if missing)
        with open(self.filepath, 'w') as f:
            json.dump({"token": token}, f)

    def save_session(self, session_data: dict):
        """Writes a session dict (token, username, role) to disk."""
        with open(self.filepath, 'w') as f:
            json.dump(session_data, f)

    def load_token(self):
        """Reads the token from disk if the file exists."""
        data = self.load_session()
        if data:
            return data.get('token')
        return None

    def load_session(self):
        """Reads the full session dict from disk if present."""
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                try:
                    data = json.load(f)
                    return data
                except Exception:
                    return None
        return None

    def clear_session(self):
        """
        Deletes the session file.
        This will be used for the 'adria logout' command!
        """
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

