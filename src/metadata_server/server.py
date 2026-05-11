from flask import Flask, request, jsonify
import jwt
import datetime
import os
from metadata_server.db import DatabaseManager

class AdriaServer:
    """Master Node Web Server handling REST API requests."""

    def __init__(self, db_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'metadata.db'), secret_key="super-secret-master-key-for-adriabox"):
        """
        Initializes the Flask application and the Database connection.
        """
        self.app = Flask(__name__)
        self.db = DatabaseManager(db_path)
        self.app.add_url_rule('/upload', view_func=self.upload, methods=['POST'])
        
        # This key is used to cryptographically sign the JWT tokens.
        # In a real production environment, this should be an environment variable.
        self.secret_key = secret_key
        
        # Mapping URLs to class methods (similar to mapping function pointers in C)
        self.app.add_url_rule('/health', view_func=self.health, methods=['GET'])
        self.app.add_url_rule('/register', view_func=self.register, methods=['POST'])
        self.app.add_url_rule('/login', view_func=self.login, methods=['POST'])

    def health(self):
        """Simple health check endpoint."""
        return jsonify({'status': 'ok'})

    def register(self):
        """
        Handles: Client -> Master: Request Register (Username, Plain Password)
        """
        data = request.json or {}
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"error": "Missing credentials"}), 400
            
        try:
            # The DB manager handles the bcrypt hashing internally
            self.db.register_user(username, password)
            # Master returns 201 Created
            return jsonify({"message": "User registered"}), 201
        except ValueError:
            return jsonify({"error": "Username already exists"}), 409

    def login(self):
        """
        Handles: Client -> Master: Request Login (Username, Plain Password)
        """
        data = request.json or {}
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"error": "Missing credentials"}), 400
            
        # Check hashes in DB; verify_user now returns a dict with id, username, role
        user = self.db.verify_user(username, password)

        if user:
            # Generate the stateless JWT Token including username and role
            payload = {
                'user_id': user['id'],
                'username': user['username'],
                'role': user.get('role', 'user'),
                # The token will expire in 24 hours
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
            }
            token = jwt.encode(payload, self.secret_key, algorithm='HS256')

            # Ensure token is a str for JSON transport (pyjwt may return bytes)
            if isinstance(token, bytes):
                token = token.decode('utf-8')

            # Master returns 200 OK (Auth Token) and user info
            return jsonify({"token": token, "username": user['username'], "role": user.get('role', 'user')}), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    def upload(self):
        """
        Handles the authorization request for a new file upload.
        Decides which Storage Node will receive the data.
        """
        # For now, we don't strictly verify the JWT for simplicity, 
        # but we could extract the user_id from it here.
        data = request.json or {}
        filename = data.get('filename')
        file_size = data.get('size')

        if not filename:
            return jsonify({"error": "Missing filename"}), 400

        # In a real distributed system, we would have a list of nodes 
        # and pick the one with more free space. 
        # For this laboratory, we point to our only active node.
        target_node_ip = "127.0.0.1"
        target_node_port = 7001

        # Save metadata to DB (assuming owner_id 1 for now)
        try:
            self.db.add_file(filename, chunks=1, owner_id=1)
        except Exception as e:
            return jsonify({"error": f"Database error: {e}"}), 500

        # Respond with the coordinates of the Storage Node
        return jsonify({
            "node_ip": target_node_ip,
            "node_port": target_node_port,
            "message": "Authorized"
        }), 200


    def run(self, host='0.0.0.0', port=5000):
        """Starts the Flask server loop (blocking call)."""
        self.app.run(host=host, port=port, debug=True)

if __name__ == '__main__':
    # Entry point for the Master Server
    server = AdriaServer()
    server.run()

