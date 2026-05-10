-- SQL schema for the AdriaBOX Metadata Server.
-- The runtime database is currently initialized by src/metadata_server/db.py.
-- Keep this file aligned with DatabaseManager._init_db as schema documentation.
--We will decide later if we want to use this file for initializing the database or just as documentation.
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  chunks INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  owner_id INTEGER,
  FOREIGN KEY(owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS storage_nodes (
  node_id TEXT PRIMARY KEY,
  host TEXT NOT NULL,
  client_host TEXT NOT NULL DEFAULT 'localhost',
  http_port INTEGER NOT NULL,
  tcp_port INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stored_files (
  file_id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  remote_path TEXT NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT,
  chunks_count INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stored_file_chunks (
  file_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  chunk_filename TEXT NOT NULL,
  node_id TEXT NOT NULL,
  host TEXT NOT NULL,
  client_host TEXT NOT NULL,
  tcp_port INTEGER NOT NULL,
  size INTEGER NOT NULL,
  sha256 TEXT,
  PRIMARY KEY (file_id, chunk_index),
  FOREIGN KEY(file_id) REFERENCES stored_files(file_id),
  FOREIGN KEY(node_id) REFERENCES storage_nodes(node_id)
);
