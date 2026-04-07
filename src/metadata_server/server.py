from flask import Flask, request, jsonify
import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'metadata.db')

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            chunks INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.before_first_request
def startup():
    init_db()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/store', methods=['POST'])
def store_metadata():
    data = request.json or {}
    filename = data.get('filename')
    chunks = int(data.get('chunks', 1))
    if not filename:
        return jsonify({'error': 'filename required'}), 400
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO files (filename, chunks, created_at) VALUES (?, ?, ?)',
                (filename, chunks, datetime.utcnow().isoformat()))
    fid = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'id': fid, 'filename': filename}), 201

@app.route('/files', methods=['GET'])
def list_files():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, filename, chunks, created_at FROM files')
    rows = cur.fetchall()
    conn.close()
    files = [{'id': r[0], 'filename': r[1], 'chunks': r[2], 'created_at': r[3]} for r in rows]
    return jsonify(files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
