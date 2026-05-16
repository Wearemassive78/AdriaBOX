import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

class DatabaseManager:
    """Handles all SQLite database operations for the Metadata Server."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row 
        return conn

    def _init_db(self):
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

            # Table for Files (Metadata) - ADDED size COLUMN
            cur.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    chunks INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    owner_id INTEGER,
                    FOREIGN KEY(owner_id) REFERENCES users(id)
                )
            ''')

            # Table for Chunks routing - ADDED size COLUMN
            cur.execute('''
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    chunk_filename TEXT NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(file_id) REFERENCES files(id)
                )
            ''')

            cur.execute("PRAGMA table_info(users)")
            cols = [r[1] for r in cur.fetchall()]
            if 'role' not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

            conn.commit()

    def register_user(self, username, plain_password, role="user"):
        hashed_pw = generate_password_hash(plain_password)
        with self._get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                            (username, hashed_pw, role))
                conn.commit()
                return cur.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError("Username already exists")

    def verify_user(self, username, plain_password):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT id, username, password_hash, role FROM users WHERE username = ?', (username,))
            user = cur.fetchone()
            if user and check_password_hash(user['password_hash'], plain_password):
                return {'id': user['id'], 'username': user['username'], 'role': user['role']}
            return None

    def add_file(self, filename, size, chunks, owner_id):
        """Records basic file metadata including size."""
        from datetime import datetime
        created_at = datetime.now().isoformat()

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO files (filename, size, chunks, created_at, owner_id) VALUES (?, ?, ?, ?, ?)',
                (filename, size, chunks, created_at, owner_id)
            )
            conn.commit()
            return cur.lastrowid

    def save_chunk_metadata(self, file_id, chunk_index, node_id, chunk_filename, size):
        """Records specific storage node and chunk size."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO chunks (file_id, chunk_index, node_id, chunk_filename, size) VALUES (?, ?, ?, ?, ?)',
                (file_id, chunk_index, node_id, chunk_filename, size)
            )
            conn.commit()

    def get_file_by_name(self, filename):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM files WHERE filename = ? ORDER BY id DESC LIMIT 1', (filename,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_chunks_by_file_id(self, file_id):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM chunks WHERE file_id = ? ORDER BY chunk_index ASC', (file_id,))
            return [dict(row) for row in cur.fetchall()]

    def get_user_files(self, user_id):
        """
        Retrieves all files owned by a specific user.
        Essential for the 'ls' command.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            # We select the necessary info, ordered by newest first
            cur.execute('''
                SELECT filename, size, chunks, created_at 
                FROM files 
                WHERE owner_id = ? 
                ORDER BY id DESC
            ''', (user_id,))
            return [dict(row) for row in cur.fetchall()]

    def delete_file(self, file_id):
        """
        Removes a file and all its chunk mappings from the database.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('DELETE FROM chunks WHERE file_id = ?', (file_id,))
            cur.execute('DELETE FROM files WHERE id = ?', (file_id,))
            conn.commit()

    def get_user_quota(self, owner_id):
        """
        Calculates the total storage footprint for a specific user.
        Returns the total sum of bytes across all owned files.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT SUM(size) as total_size FROM files WHERE owner_id = ?', 
                (owner_id,)
            )
            result = cur.fetchone()
            return result['total_size'] or 0

    def rename_file(self, file_id, new_filename):
        """
        Updates the absolute path/filename of an existing file.
        Used for moving and renaming operations (S3-style).
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                'UPDATE files SET filename = ? WHERE id = ?', 
                (new_filename, file_id)
            )
            conn.commit()

