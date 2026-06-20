"""Tests for Flask metadata server routes and HTTP error responses."""
from unittest.mock import Mock

import pytest

import metadata_server.server as server


@pytest.fixture
def route_client(monkeypatch):
    manager = Mock()
    manager.db = Mock()
    manager.storage_nodes = []
    manager.authorize_request.return_value = {
        "user_id": 10,
        "username": "mario",
        "role": "user",
    }
    monkeypatch.setattr(server, "manager", manager)

    server.app.config.update(TESTING=True)
    with server.app.test_client() as client:
        yield client, manager


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": "mario"},
        {"password": "password123"},
    ],
)
def test_register_rejects_missing_credentials(route_client, payload):
    client, manager = route_client

    response = client.post("/register", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": "Missing credentials"}
    manager.db.register_user.assert_not_called()


def test_register_creates_user(route_client):
    client, manager = route_client

    response = client.post(
        "/register",
        json={"username": "mario", "password": "password123"},
    )

    assert response.status_code == 201
    assert response.get_json() == {"message": "Registration successful"}
    manager.db.register_user.assert_called_once_with("mario", "password123")


def test_register_returns_conflict_for_existing_username(route_client):
    client, manager = route_client
    manager.db.register_user.side_effect = ValueError("Username already exists")

    response = client.post(
        "/register",
        json={"username": "mario", "password": "password123"},
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "Username already exists"}


def test_login_rejects_invalid_credentials(route_client):
    client, manager = route_client
    manager.db.verify_user.return_value = None

    response = client.post(
        "/login",
        json={"username": "mario", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "Username o password non corretti."
    }


def test_login_returns_token_and_user_role(route_client):
    client, manager = route_client
    manager.db.verify_user.return_value = {
        "id": 10,
        "username": "mario",
        "role": "admin",
    }
    manager.generate_token.return_value = "jwt-token"

    response = client.post(
        "/login",
        json={"username": "mario", "password": "password123"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "token": "jwt-token",
        "username": "mario",
        "role": "admin",
    }
    manager.generate_token.assert_called_once_with("mario")


def test_protected_route_rejects_missing_authorization(route_client):
    client, manager = route_client
    manager.authorize_request.side_effect = PermissionError(
        "Missing or malformed Authorization token."
    )

    response = client.get("/files/list")

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "Missing or malformed Authorization token."
    }


def test_upload_plan_returns_manager_plan(route_client):
    client, manager = route_client
    manager.build_upload_plan.return_value = {
        "file_id": 42,
        "remote_path": "/docs/demo.txt",
        "chunks": [],
    }

    response = client.post(
        "/files/upload-plan",
        json={"filename": "demo.txt", "size": 100, "remote_dir": "/docs"},
        headers={"Authorization": "Bearer jwt-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["file_id"] == 42
    manager.build_upload_plan.assert_called_once_with(
        {
            "user_id": 10,
            "username": "mario",
            "role": "user",
        },
        "demo.txt",
        100,
        "/docs",
    )


def test_download_plan_translates_missing_file_to_404(route_client):
    client, manager = route_client
    manager.build_download_plan.side_effect = FileNotFoundError("File not found.")

    response = client.get(
        "/files/download-plan",
        query_string={"filename": "/missing.txt"},
        headers={"Authorization": "Bearer jwt-token"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "File not found."}


def test_cluster_status_rejects_non_admin_user(route_client):
    client, _ = route_client

    response = client.get(
        "/cluster-status",
        headers={"Authorization": "Bearer jwt-token"},
    )

    assert response.status_code == 403
    assert response.get_json() == {"error": "Admin role required."}


def test_cluster_status_returns_configured_nodes_for_admin(route_client):
    client, manager = route_client
    manager.authorize_request.return_value = {
        "user_id": 1,
        "username": "admin",
        "role": "admin",
    }
    manager.storage_nodes = [
        {
            "node_id": "node-a",
            "host": "storage-a",
            "tcp_port": 7001,
        }
    ]

    response = client.get(
        "/cluster-status",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["metadata"]["status"] == "ok"
    assert response.get_json()["nodes"] == [
        {
            "node_id": "node-a",
            "status": "ok",
            "host": "storage-a",
            "http_port": 5001,
            "tcp_port": 7001,
            "storage_dir": "/app/storage/node-a",
        }
    ]


def test_remove_file_hides_unauthorized_file_as_not_found(route_client):
    client, manager = route_client
    manager.db.get_file_by_name.return_value = {
        "id": 42,
        "filename": "/private.txt",
        "owner_id": 99,
    }

    response = client.delete(
        "/files/remove",
        query_string={"filename": "/private.txt"},
        headers={"Authorization": "Bearer jwt-token"},
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "File not found."}
    manager.db.delete_file.assert_not_called()
