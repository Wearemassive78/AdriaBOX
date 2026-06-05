"""Flask endpoint controller routing for the AdriaBOX Metadata Server."""
import os
from flask import Flask, request, jsonify
from metadata_server.manager import AdriaMetadataManager

app = Flask(__name__)

manager = AdriaMetadataManager(
    db_path=os.environ.get("ADRIABOX_DB_PATH", "data/metadata.db"),
    storage_nodes_cfg=os.environ.get("ADRIABOX_STORAGE_NODES", "")
)

def _auth_and_route(handler_func, *args, **kwargs):
    """Aspect-oriented helper to handle authorization wrapping and standardized error translation."""
    try:
        user_ctx = manager.authorize_request(request.headers.get("Authorization"))
        return handler_func(user_ctx, *args, **kwargs)
    except PermissionError as e: 
        return jsonify({"error": str(e)}), 403
    except FileNotFoundError as e: 
        return jsonify({"error": str(e)}), 404
    except Exception as e: 
        return jsonify({"error": str(e)}), 500


@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    username, password = data.get("username"), data.get("password")
    if not username or not password: 
        return jsonify({"error": "Missing credentials"}), 400
    try:
        manager.db.register_user(username, password)
        return jsonify({"message": "Registration successful"}), 201
    except ValueError as e: 
        return jsonify({"error": str(e)}), 409
    except Exception as e: 
        return jsonify({"error": str(e)}), 500


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    username, password = data.get("username"), data.get("password")
    
    # Authenticate through secure Werkzeug cryptographic hash evaluation
    user = manager.db.verify_user(username, password)
    if not user:
        return jsonify({"error": "Username o password non corretti."}), 401
        
    token = manager.generate_token(username)
    return jsonify({"token": token, "username": username, "role": user["role"]}), 200


@app.route("/files/upload-plan", methods=["POST"])
def upload_plan():
    def _logic(user_ctx):
        data = request.json or {}
        plan = manager.build_upload_plan(user_ctx, data.get("filename"), data.get("size"), data.get("remote_dir"))
        return jsonify(plan), 200
    return _auth_and_route(_logic)


@app.route("/files/complete", methods=["POST"])
def upload_complete():
    def _logic(user_ctx):
        data = request.json or {}
        manager.commit_file_chunks(int(data.get("file_id")), data.get("chunks", []))
        return jsonify({"message": "Synchronization complete."}), 200
    return _auth_and_route(_logic)


@app.route("/files/download-plan", methods=["GET"])
def download_plan():
    def _logic(user_ctx):
        plan = manager.build_download_plan(user_ctx, request.args.get("filename"))
        return jsonify(plan), 200
    return _auth_and_route(_logic)


@app.route("/files/list", methods=["GET"])
def list_files():
    def _logic(user_ctx):
        directory = request.args.get("directory", "/")
        files = manager.db.list_files_in_dir(directory, user_ctx["user_id"], user_ctx["role"])
        return jsonify({"files": files}), 200
    return _auth_and_route(_logic)


@app.route("/files/remove", methods=["DELETE"])
def remove_file():
    def _logic(user_ctx):
        filename = request.args.get("filename")
        if not filename.startswith("/"): filename = "/" + filename
        file_info = manager.db.get_file_by_name(filename)
        if not file_info: raise FileNotFoundError("File not found.")
        if file_info["owner_id"] != user_ctx["user_id"] and user_ctx["role"] != "admin": 
            raise PermissionError("Forbidden.")
            
        deletion_targets = manager.get_file_deletion_plan(file_info["id"])
        manager.db.delete_file(file_info["id"])
        return jsonify({"message": "Metadata and targets resolved.", "chunks": deletion_targets}), 200
    return _auth_and_route(_logic)


@app.route("/files/mkdir", methods=["POST"])
def mkdir():
    def _logic(user_ctx):
        data = request.json or {}
        manager.db.add_file(data.get("path"), size=0, chunks=0, owner_id=user_ctx["user_id"])
        return jsonify({"message": "Directory prefix registered successfully."}), 201
    return _auth_and_route(_logic)


@app.route("/files/quota", methods=["GET"])
def get_quota():
    def _logic(user_ctx):
        total = manager.db.get_user_quota(user_ctx["user_id"])
        return jsonify({"total_bytes": total}), 200
    return _auth_and_route(_logic)


@app.route("/cluster-status", methods=["GET"])
def cluster_status():
    def _logic(user_ctx):
        if user_ctx["role"] != "admin": raise PermissionError("Admin role required.")
        nodes_report = [{
            "node_id": n["node_id"], "status": "ok", "host": n["host"], "http_port": 5001, "tcp_port": n["tcp_port"], "storage_dir": f"/app/storage/{n['node_id']}"
        } for n in manager.storage_nodes]
        return jsonify({"metadata": {"status": "ok", "url": request.url_root}, "nodes": nodes_report}), 200
    return _auth_and_route(_logic)


@app.route("/admin/users", methods=["GET"])
def admin_list_users():
    def _logic(user_ctx):
        if user_ctx["role"] != "admin": raise PermissionError("Admin role required.")
        return jsonify({"users": manager.db.get_all_users_with_usage()}), 200
    return _auth_and_route(_logic)


@app.route("/admin/userdel", methods=["POST"])
def admin_delete_user():
    def _logic(user_ctx):
        if user_ctx["role"] != "admin": raise PermissionError("Admin role required.")
        data = request.json or {}
        target_username, admin_password = data.get("target_username"), data.get("admin_password")
        
        admin_user = manager.db.verify_user(user_ctx["username"], admin_password)
        if not admin_user: raise PermissionError("Administrative authentication failed.")
            
        target_user = manager.db.get_user_by_username(target_username)
        if not target_user: raise FileNotFoundError("Target user missing.")
        
        all_deletion_targets = []
        for f in manager.db.get_user_files(target_user["id"]):
            all_deletion_targets.extend(manager.get_file_deletion_plan(f["id"]))
            
        manager.db.delete_user_and_metadata(target_user["id"])
        return jsonify({"message": f"User '{target_username}' and assets purged.", "chunks": all_deletion_targets}), 200
    return _auth_and_route(_logic)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

