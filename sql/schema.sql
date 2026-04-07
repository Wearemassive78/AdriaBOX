-- SQL schema for Metadata Server
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  chunks INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
