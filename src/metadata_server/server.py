from flask import Flask, request, jsonify
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# Setup paths for the database
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'metadata.db')

app = Flask(__name__)

def init_db():
    """Initializes the SQLite database and creates the files table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # In C, this is equivalent to executing a statement with sqlite3_exec()
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

@app.route('/health', methods=['GET'])
def health():
    """Simple health check endpoint."""
    return jsonify({'status': 'ok'})

@app.route('/store', methods=['POST'])
def store_metadata():
    """Registers new file metadata in the database."""
    # Equivalent to parsing a JSON body with a library like cJSON in C
    data = request.json or {}
    filename = data.get('filename')
    chunks = int(data.get('chunks', 1))

    if not filename:
        return jsonify({'error': 'filename required'}), 400

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Using '?' placeholders prevents SQL Injection (similar to prepared statements)
    cur.execute('INSERT INTO files (filename, chunks, created_at) VALUES (?, ?, ?)',
                (filename, chunks, datetime.utcnow().isoformat()))
    
    fid = cur.lastrowid # Get the last inserted ID (AUTOINCREMENT)
    conn.commit()
    conn.close() # Fixed: Ensure connection is closed inside the function
    
    return jsonify({'id': fid, 'filename': filename}), 201


@app.route('/upload', methods=['POST'])
def upload_file():
    """Accepts a file upload, saves it to disk and registers metadata."""
    if 'file' not in request.files:
        return jsonify({'error': 'file field is required'}), 400

    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'filename required'}), 400

    filename = secure_filename(f.filename)
    save_dir = os.path.join(BASE_DIR, 'data')
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)
    f.save(save_path)

    # register metadata entry in the database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO files (filename, chunks, created_at) VALUES (?, ?, ?)',
                (filename, 1, datetime.utcnow().isoformat()))
    fid = cur.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'id': fid, 'filename': filename, 'path': save_path}), 201

@app.route('/files', methods=['GET'])
def list_files():
    """Returns a list of all files registered in the system."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, filename, chunks, created_at FROM files')
    rows = cur.fetchall()
    conn.close()
    
    # List comprehension: a compact way to build a list of dictionaries
    files = [{'id': r[0], 'filename': r[1], 'chunks': r[2], 'created_at': r[3]} for r in rows]
    return jsonify(files)

if __name__ == '__main__':
    # Initialize the database before starting the server
    init_db()
    # Start the Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)
