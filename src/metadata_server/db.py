import sqlite3
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class DatabaseManager:
    """Handles all SQLite database operations for the Metadata Server."""

    def __init__(self, db_path: str):
        """
        Equivalent to initializing a struct holding the database file path.
        We don't keep the connection constantly open to avoid threading issues.
        """
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        """
        Private helper method to open a database connection.
        Think of this as a wrapper around sqlite3_open() in C.
        """
        conn = sqlite3.connect(self.db_path)
        # This allows us to access columns by name (e.g., row['username'])
        conn.row_factory = sqlite3.Row 
        return conn

    def _init_db(self):
        """Creates the necessary tables if they don't exist."""
        # The 'with' statement in Python acts like an automatic cleanup mechanism.
        # It ensures that 'conn.close()' is automatically called at the end of the block,
        # preventing resource leaks, just like a deferred 'fclose()' in C.
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # Table for Users (Authentication)
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user'
                )
            ''')
            
            # Table for Files (Metadata) - migrated from the old procedural code
            cur.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    chunks INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    owner_id INTEGER,
                    FOREIGN KEY(owner_id) REFERENCES users(id)
                )
            ''')

            cur.execute('''
                CREATE TABLE IF NOT EXISTS storage_nodes (
                    node_id TEXT PRIMARY KEY,
                    host TEXT NOT NULL,
                    http_port INTEGER NOT NULL,
                    tcp_port INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    last_seen TEXT NOT NULL
                )
            ''')

            # Ensure older databases get the 'role' column added if missing
            cur.execute("PRAGMA table_info(users)")
            cols = [r[1] for r in cur.fetchall()]
            if 'role' not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

            conn.commit()

    def register_storage_node(self, node_id, host, http_port, tcp_port, status='active'):
        """Registers or refreshes a storage node heartbeat."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO storage_nodes (node_id, host, http_port, tcp_port, status, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    host = excluded.host,
                    http_port = excluded.http_port,
                    tcp_port = excluded.tcp_port,
                    status = excluded.status,
                    last_seen = excluded.last_seen
            ''', (node_id, host, http_port, tcp_port, status, now))
            conn.commit()

        return {
            'node_id': node_id,
            'host': host,
            'http_port': http_port,
            'tcp_port': tcp_port,
            'status': status,
            'last_seen': now,
        }

    def list_storage_nodes(self):
        """Returns all registered storage nodes ordered by node id."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT node_id, host, http_port, tcp_port, status, last_seen
                FROM storage_nodes
                ORDER BY node_id
            ''')
            return [dict(row) for row in cur.fetchall()]

    def register_user(self, username, plain_password):
        """
        Registers a new user with a securely hashed password.
        Returns the user ID on success, or raises an Exception if the user exists.
        """
        hashed_pw = generate_password_hash(plain_password)
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            try:
                # The '?' placeholders prevent SQL Injection
                cur.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                            (username, hashed_pw, 'user'))
                conn.commit()
                return cur.lastrowid
            except sqlite3.IntegrityError:
                # UNIQUE constraint failed (username already exists)
                raise ValueError("Username already exists")

    def verify_user(self, username, plain_password):
        """
        Checks if the username exists and the password matches the hash.
        Returns the user ID if successful, or None if authentication fails.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT id, username, password_hash, role FROM users WHERE username = ?', (username,))
            user = cur.fetchone()

            if user and check_password_hash(user['password_hash'], plain_password):
                return {'id': user['id'], 'username': user['username'], 'role': user['role']}

            return None
