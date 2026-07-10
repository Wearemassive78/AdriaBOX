import sqlite3
from datetime import datetime
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
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table for Files (Metadata)
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

            # Table for Chunks routing
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
        """Securely validate user credentials using Werkzeug crypt hashes."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT id, username, password_hash, role FROM users WHERE username = ?', (username,))
            user = cur.fetchone()
            if user and check_password_hash(user['password_hash'], plain_password):
                return {'id': user['id'], 'username': user['username'], 'role': user['role']}
            return None

    def get_user_by_username(self, username):
        """Fetch basic user details required for token generation and admin controls."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT id, username, role FROM users WHERE username = ?', (username,))
            row = cur.fetchone()
            return dict(row) if row else None

    def add_file(self, filename, size, chunks, owner_id):
        """Records basic file metadata and returns the generated primary key ID."""
        created_at = datetime.now().isoformat()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO files (filename, size, chunks, created_at, owner_id) VALUES (?, ?, ?, ?, ?)',
                (filename, size, chunks, created_at, owner_id)
            )
            conn.commit()
            return cur.lastrowid

    def add_chunk(self, file_id, chunk_index, node_id, chunk_filename, size):
        """Maps a chunk partition to its respective primary storage node target."""
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
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT id, filename, size, chunks, created_at FROM files WHERE owner_id = ? ORDER BY id DESC', (user_id,))
            return [dict(row) for row in cur.fetchall()]

    def list_files_in_dir(self, directory, user_id, role):
        """List files filtering by tenant visibility or admin scope."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            if role == "admin":
                cur.execute('SELECT filename, size, chunks FROM files')
            else:
                cur.execute('SELECT filename, size, chunks FROM files WHERE owner_id = ?', (user_id,))
            
            all_files = [dict(row) for row in cur.fetchall()]
            
            # Simple directory virtualization matching your original logic
            results = []
            seen = set()
            prefix = directory.rstrip("/") + "/"
            if prefix == "/": prefix = "/"

            for f in all_files:
                path = f["filename"]
                if directory == "/" or path.startswith(prefix):
                    rel_path = path if directory == "/" else path[len(prefix):]
                    parts = rel_path.strip("/").split("/")
                    if parts and parts[0]:
                        name = parts[0]
                        if name in seen: continue
                        seen.add(name)
                        if len(parts) > 1:
                            results.append({"filename": name, "is_dir": True, "size": 0, "chunks": 0})
                        else:
                            results.append({"filename": name, "is_dir": False, "size": f["size"], "chunks": f["chunks"]})
            return results

    def delete_file(self, file_id):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('DELETE FROM chunks WHERE file_id = ?', (file_id,))
            cur.execute('DELETE FROM files WHERE id = ?', (file_id,))
            conn.commit()

    def get_user_quota(self, owner_id):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT SUM(size) as total_size FROM files WHERE owner_id = ?', (owner_id,))
            result = cur.fetchone()
            return result['total_size'] or 0

    def get_all_users_with_usage(self):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT u.id, u.username, u.role, u.created_at,
                       COALESCE(SUM(f.size), 0) as total_used
                FROM users u
                LEFT JOIN files f ON u.id = f.owner_id
                GROUP BY u.id
                ORDER BY total_used DESC
            ''')
            return [dict(row) for row in cur.fetchall()]

    def delete_user_and_metadata(self, target_user_id):
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute('DELETE FROM chunks WHERE file_id IN (SELECT id FROM files WHERE owner_id = ?)', (target_user_id,))
            cur.execute('DELETE FROM files WHERE owner_id = ?', (target_user_id,))
            cur.execute('DELETE FROM users WHERE id = ?', (target_user_id,))
            conn.commit()

