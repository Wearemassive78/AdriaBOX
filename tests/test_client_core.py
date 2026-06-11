"""Tests for the high-level AdriaClient facade behavior."""
import pytest
from unittest.mock import Mock, patch

from client.core import AdriaClient


def make_client(session_data=None):
    with (
        patch("client.core.SessionManager") as session_manager_cls,
        patch("client.core.AdriaHTTPClient") as http_client_cls,
        patch("client.core.AdriaTransferManager") as transfer_manager_cls,
    ):
        session_manager = Mock()
        session_manager.load_session.return_value = session_data
        session_manager_cls.return_value = session_manager

        http_client = Mock()
        http_client_cls.return_value = http_client

        transfer_manager = Mock()
        transfer_manager_cls.return_value = transfer_manager

        client = AdriaClient("http://metadata:5000", request_timeout=3.0)

    return client, session_manager, http_client, transfer_manager


def test_init_restores_saved_session_and_auth_header():
    client, _, http_client, _ = make_client(
        {
            "token": "saved-token",
            "username": "mario",
            "crypto_key": "saved-key",
        }
    )

    assert client.auth_token == "saved-token"
    assert client.current_username == "mario"
    assert client.crypto_key == "saved-key"
    http_client.update_auth_header.assert_called_once_with("saved-token")


def test_login_stores_token_crypto_key_and_session():
    client, session_manager, http_client, _ = make_client()
    http_client.login.return_value = {"token": "jwt-token", "username": "mario"}

    with patch("client.core.CryptoManager.derive_key", return_value="derived-key"):
        result = client.login("mario", "password123")

    assert result == {"token": "jwt-token", "username": "mario"}
    assert client.auth_token == "jwt-token"
    assert client.current_username == "mario"
    assert client.crypto_key == "derived-key"
    http_client.update_auth_header.assert_called_once_with("jwt-token")
    session_manager.save_session.assert_called_once_with(
        "jwt-token",
        "mario",
        "derived-key",
    )


def test_logout_clears_session_and_auth_header():
    client, session_manager, http_client, _ = make_client(
        {
            "token": "saved-token",
            "username": "mario",
            "crypto_key": "saved-key",
        }
    )
    http_client.update_auth_header.reset_mock()

    client.logout()

    assert client.auth_token is None
    assert client.current_username is None
    assert client.crypto_key is None
    session_manager.clear_session.assert_called_once_with()
    http_client.update_auth_header.assert_called_once_with(None)


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("list_files", ("/",)),
        ("rm", ("/demo.txt",)),
        ("mkdir", ("/docs",)),
        ("rmdir", ("/docs",)),
        ("mv", ("/old.txt", "/new.txt")),
        ("get_quota", ()),
        ("cluster_status", ()),
        ("admin_list_users", ()),
        ("admin_delete_user", ("mario", "admin-password")),
    ],
)
def test_authenticated_methods_reject_missing_token(method_name, args):
    client, _, _, _ = make_client()

    with pytest.raises(Exception, match="Authentication required"):
        getattr(client, method_name)(*args)


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("upload", ("demo.txt", "/")),
        ("download", ("/demo.txt",)),
    ],
)
def test_file_transfer_methods_require_token_and_crypto_key(method_name, args):
    client, _, _, _ = make_client()

    with pytest.raises(Exception, match="Authentication and encryption key required"):
        getattr(client, method_name)(*args)


def test_upload_gets_plan_transfers_chunks_and_completes_metadata():
    client, _, http_client, transfer_manager = make_client()
    client.auth_token = "jwt-token"
    client.crypto_key = "derived-key"

    plan_chunks = [{"index": 0, "chunk_filename": "1_0_demo.txt.chunk"}]
    uploaded_chunks = [{"index": 0, "chunk_filename": "1_0_demo.txt.chunk", "size": 11}]
    http_client.get_upload_plan.return_value = {
        "file_id": 1,
        "remote_path": "/docs/demo.txt",
        "chunks": plan_chunks,
    }
    transfer_manager.upload_file_chunks.return_value = uploaded_chunks
    http_client.complete_upload.return_value = {"message": "Synchronization complete."}

    with patch("client.core.os.path.getsize", return_value=11):
        result = client.upload("demo.txt", remote_dir="/docs")

    http_client.get_upload_plan.assert_called_once_with("demo.txt", 11, "/docs")
    transfer_manager.upload_file_chunks.assert_called_once_with(
        "demo.txt",
        plan_chunks,
        "derived-key",
    )
    http_client.complete_upload.assert_called_once_with(
        1,
        "/docs/demo.txt",
        uploaded_chunks,
        11,
    )
    assert result == {
        "remote_path": "/docs/demo.txt",
        "chunks": uploaded_chunks,
        "message": "Synchronization complete.",
    }


def test_download_gets_plan_and_writes_to_destination():
    client, _, http_client, transfer_manager = make_client()
    client.auth_token = "jwt-token"
    client.crypto_key = "derived-key"

    plan_chunks = [{"index": 0, "chunk_filename": "1_0_demo.txt.chunk"}]
    http_client.get_download_plan.return_value = {"chunks": plan_chunks}

    result = client.download("/demo.txt", local_destination="downloaded-demo.txt")

    http_client.get_download_plan.assert_called_once_with("/demo.txt")
    transfer_manager.download_file_chunks.assert_called_once_with(
        "downloaded-demo.txt",
        plan_chunks,
        "derived-key",
    )
    assert result == "downloaded-demo.txt"
