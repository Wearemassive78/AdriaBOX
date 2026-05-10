from flask import Flask, request, jsonify
import jwt
import datetime
import os
import math
import uuid
from metadata_server.db import DatabaseManager

class AdriaServer:
    """Master Node Web Server handling REST API requests."""

    def __init__(self, db_path=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'metadata.db'), secret_key="super-secret-master-key-for-adriabox", db=None):
        """
        Initializes the Flask application and the Database connection.
        """
        self.app = Flask(__name__)
        self.db = db or DatabaseManager(db_path)
        
        # This key is used to cryptographically sign the JWT tokens.
        # In a real production environment, this should be an environment variable.
        self.secret_key = secret_key
        
        # Mapping URLs to class methods (similar to mapping function pointers in C)
        self.app.add_url_rule('/health', view_func=self.health, methods=['GET'])
        self.app.add_url_rule('/register', view_func=self.register, methods=['POST'])
        self.app.add_url_rule('/login', view_func=self.login, methods=['POST'])
        self.app.add_url_rule('/nodes', view_func=self.list_nodes, methods=['GET'])
        self.app.add_url_rule('/nodes', view_func=self.register_node, methods=['POST'])
        self.app.add_url_rule('/files/upload-plan', view_func=self.create_upload_plan, methods=['POST'])
        self.app.add_url_rule('/files/complete', view_func=self.complete_upload, methods=['POST'])

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

    def register_node(self):
        """Registers or refreshes a storage node in the cluster registry."""
        data = request.json or {}
        node_id = data.get('node_id')
        host = data.get('host')
        http_port = data.get('http_port')
        tcp_port = data.get('tcp_port')

        if not node_id or not host or not http_port or not tcp_port:
            return jsonify({"error": "Missing node registration fields"}), 400

        try:
            node = self.db.register_storage_node(
                node_id=node_id,
                host=host,
                http_port=int(http_port),
                tcp_port=int(tcp_port),
                status=data.get('status', 'active'),
                client_host=data.get('client_host', 'localhost'),
            )
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid node port"}), 400

        return jsonify(node), 201

    def list_nodes(self):
        """Lists registered storage nodes."""
        return jsonify(self.db.list_storage_nodes())

    def create_upload_plan(self):
        """Creates a placement plan that splits a file across active storage nodes."""
        data = request.json or {}
        filename = data.get('filename')
        size = data.get('size')
        remote_dir = data.get('remote_dir', '/')

        if not filename or size is None:
            return jsonify({"error": "Missing upload plan fields"}), 400

        try:
            size = int(size)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid file size"}), 400

        nodes = [
            node for node in self.db.list_storage_nodes()
            if node.get('status') == 'active'
        ]
        if not nodes:
            return jsonify({"error": "No active storage nodes available"}), 503

        chunk_count = min(3, len(nodes), max(1, size))
        chunk_size = math.ceil(size / chunk_count) if size else 0
        file_id = str(uuid.uuid4())

        chunks = []
        for index in range(chunk_count):
            node = nodes[index % len(nodes)]
            offset = index * chunk_size
            current_size = max(0, min(chunk_size, size - offset))
            chunk_filename = f"{file_id}.chunk{index}"
            chunks.append({
                "index": index,
                "offset": offset,
                "size": current_size,
                "chunk_filename": chunk_filename,
                "node_id": node['node_id'],
                "host": node['host'],
                "client_host": node.get('client_host', 'localhost'),
                "tcp_port": node['tcp_port'],
            })

        return jsonify({
            "file_id": file_id,
            "filename": os.path.basename(filename),
            "remote_path": os.path.join(remote_dir, os.path.basename(filename)).replace("\\", "/"),
            "size": size,
            "chunks": chunks,
        })

    def complete_upload(self):
        """Persists uploaded file metadata after all chunks have been stored."""
        data = request.json or {}
        required = ('file_id', 'filename', 'remote_path', 'size', 'chunks')
        if any(data.get(field) is None for field in required):
            return jsonify({"error": "Missing upload completion fields"}), 400

        stored = self.db.save_stored_file(
            file_id=data['file_id'],
            filename=data['filename'],
            remote_path=data['remote_path'],
            size=int(data['size']),
            sha256=data.get('sha256'),
            chunks=data['chunks'],
        )

        return jsonify(stored), 201

    def run(self, host='0.0.0.0', port=5000):
        """Starts the Flask server loop (blocking call)."""
        self.app.run(host=host, port=port, debug=True)

if __name__ == '__main__':
    # Entry point for the Master Server
    server = AdriaServer()
    server.run()

