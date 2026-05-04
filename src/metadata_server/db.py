import sqlite3
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
            # Ensure older databases get the 'role' column added if missing
            cur.execute("PRAGMA table_info(users)")
            cols = [r[1] for r in cur.fetchall()]
            if 'role' not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

            conn.commit()

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

