from flask import Flask, request, jsonify
import jwt
import datetime
from metadata_server.db import DatabaseManager

class AdriaServer:
    """Master Node Web Server handling REST API requests."""

    def __init__(self, db_path="metadata.db", secret_key="super-secret-master-key"):
        """
        Initializes the Flask application and the Database connection.
        """
        self.app = Flask(__name__)
        self.db = DatabaseManager(db_path)
        
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
            
        # Check hashes in DB
        user_id = self.db.verify_user(username, password)
        
        if user_id:
            # Generate the stateless JWT Token
            payload = {
                'user_id': user_id,
                # The token will expire in 24 hours
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }
            token = jwt.encode(payload, self.secret_key, algorithm='HS256')
            
            # Master returns 200 OK (Auth Token)
            return jsonify({"token": token}), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    def run(self, host='0.0.0.0', port=5000):
        """Starts the Flask server loop (blocking call)."""
        self.app.run(host=host, port=port, debug=True)

if __name__ == '__main__':
    # Entry point for the Master Server
    server = AdriaServer()
    server.run()

