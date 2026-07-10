"""Tests for HTTP requests and response handling in AdriaHTTPClient."""
from unittest.mock import Mock, patch

import pytest
import requests

from client.exceptions import BackendServerError
from client.http_client import AdriaHTTPClient


@pytest.fixture
def http_client():
    with patch("client.http_client.requests.Session") as session_cls:
        session = Mock()
        session.headers = {}
        session_cls.return_value = session
        client = AdriaHTTPClient("http://metadata:5000", request_timeout=3.0)

    return client, session


def successful_response(payload):
    response = Mock()
    response.ok = True
    response.json.return_value = payload
    return response


def test_update_auth_header_adds_and_removes_bearer_token(http_client):
    client, session = http_client

    client.update_auth_header("jwt-token")
    assert session.headers["Authorization"] == "Bearer jwt-token"

    client.update_auth_header(None)
    assert "Authorization" not in session.headers


@pytest.mark.parametrize(
    ("method_name", "arguments", "path", "payload"),
    [
        (
            "register",
            ("mario", "password123"),
            "/register",
            {"username": "mario", "password": "password123"},
        ),
        (
            "login",
            ("mario", "password123"),
            "/login",
            {"username": "mario", "password": "password123"},
        ),
        (
            "get_upload_plan",
            ("demo.txt", 100, "/docs"),
            "/files/upload-plan",
            {"filename": "demo.txt", "size": 100, "remote_dir": "/docs"},
        ),
        (
            "mkdir",
            ("/docs",),
            "/files/mkdir",
            {"path": "/docs"},
        ),
        (
            "admin_delete_user_metadata",
            ("luigi", "admin-password"),
            "/admin/userdel",
            {
                "target_username": "luigi",
                "admin_password": "admin-password",
            },
        ),
    ],
)
def test_post_methods_send_expected_json(
    http_client,
    method_name,
    arguments,
    path,
    payload,
):
    client, session = http_client
    session.post.return_value = successful_response({"result": "ok"})

    result = getattr(client, method_name)(*arguments)

    assert result == {"result": "ok"}
    session.post.assert_called_once_with(
        f"http://metadata:5000{path}",
        json=payload,
        timeout=3.0,
    )


def test_complete_upload_sends_file_and_chunk_metadata(http_client):
    client, session = http_client
    chunks = [{"index": 0, "chunk_filename": "42_0_demo.txt.chunk"}]
    session.post.return_value = successful_response(
        {"message": "Synchronization complete."}
    )

    result = client.complete_upload(42, "/docs/demo.txt", chunks, 100)

    assert result == {"message": "Synchronization complete."}
    session.post.assert_called_once_with(
        "http://metadata:5000/files/complete",
        json={
            "file_id": 42,
            "remote_path": "/docs/demo.txt",
            "chunks": chunks,
            "size": 100,
        },
        timeout=3.0,
    )


@pytest.mark.parametrize(
    ("method_name", "arguments", "path", "params"),
    [
        (
            "get_download_plan",
            ("/demo.txt",),
            "/files/download-plan",
            {"filename": "/demo.txt"},
        ),
        (
            "list_files",
            ("/docs",),
            "/files/list",
            {"directory": "/docs"},
        ),
    ],
)
def test_get_methods_send_expected_query_parameters(
    http_client,
    method_name,
    arguments,
    path,
    params,
):
    client, session = http_client
    response_payload = {"files": []} if method_name == "list_files" else {}
    session.get.return_value = successful_response(response_payload)

    getattr(client, method_name)(*arguments)

    session.get.assert_called_once_with(
        f"http://metadata:5000{path}",
        params=params,
        timeout=3.0,
    )


def test_list_files_returns_empty_list_when_response_has_no_files(http_client):
    client, session = http_client
    session.get.return_value = successful_response({})

    assert client.list_files("/") == []


def test_get_quota_returns_zero_when_total_is_missing(http_client):
    client, session = http_client
    session.get.return_value = successful_response({})

    assert client.get_quota() == 0
    session.get.assert_called_once_with(
        "http://metadata:5000/files/quota",
        timeout=3.0,
    )


def test_remove_file_metadata_sends_delete_request(http_client):
    client, session = http_client
    session.delete.return_value = successful_response({"chunks": []})

    result = client.remove_file_metadata("/demo.txt")

    assert result == {"chunks": []}
    session.delete.assert_called_once_with(
        "http://metadata:5000/files/remove",
        params={"filename": "/demo.txt"},
        timeout=3.0,
    )


def test_mv_metadata_returns_raw_response(http_client):
    client, session = http_client
    response = successful_response({"message": "moved"})
    session.post.return_value = response

    result = client.mv_metadata("/old.txt", "/new.txt")

    assert result is response
    session.post.assert_called_once_with(
        "http://metadata:5000/files/move",
        json={"source": "/old.txt", "destination": "/new.txt"},
        timeout=3.0,
    )


def test_unwrap_response_raises_backend_error_from_server_json(http_client):
    client, _ = http_client
    response = Mock()
    response.ok = False
    response.json.return_value = {"error": "Username already exists"}

    with pytest.raises(BackendServerError, match="Username already exists"):
        client._unwrap_response(response)

    response.raise_for_status.assert_not_called()


def test_unwrap_response_falls_back_to_http_error_for_invalid_json(http_client):
    client, _ = http_client
    response = Mock()
    response.ok = False
    response.json.side_effect = requests.exceptions.JSONDecodeError(
        "invalid JSON",
        "",
        0,
    )
    response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )

    with pytest.raises(requests.exceptions.HTTPError, match="500 Server Error"):
        client._unwrap_response(response)

    response.raise_for_status.assert_called_once_with()
