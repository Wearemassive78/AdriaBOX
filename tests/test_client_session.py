"""Tests for local client session persistence."""
import json
from unittest.mock import mock_open, patch

from client.session import SessionManager


@patch("client.session.os.makedirs")
def test_save_and_load_session(_):
    manager = SessionManager("test-session.json")
    file_mock = mock_open()

    with (
        patch("client.session.open", file_mock),
        patch("client.session.os.path.exists", return_value=True),
        patch("client.session.json.dump") as dump,
        patch(
            "client.session.json.load",
            return_value={
                "token": "jwt-token",
                "username": "mario",
                "crypto_key": "secret-key",
            },
        ),
    ):
        manager.save_session("jwt-token", "mario", "secret-key")
        session = manager.load_session()

    dump.assert_called_once_with(
        {
            "token": "jwt-token",
            "username": "mario",
            "crypto_key": "secret-key",
        },
        file_mock(),
    )
    assert session["username"] == "mario"


@patch("client.session.os.makedirs")
def test_load_session_returns_none_for_missing_or_invalid_file(_):
    manager = SessionManager("test-session.json")

    with patch("client.session.os.path.exists", return_value=False):
        assert manager.load_session() is None

    with (
        patch("client.session.os.path.exists", return_value=True),
        patch("client.session.open", mock_open()),
        patch(
            "client.session.json.load",
            side_effect=json.JSONDecodeError("invalid JSON", "", 0),
        ),
    ):
        assert manager.load_session() is None


@patch("client.session.os.makedirs")
def test_clear_session_removes_existing_file(_):
    manager = SessionManager("test-session.json")

    with (
        patch("client.session.os.path.exists", return_value=True),
        patch("client.session.os.remove") as remove,
    ):
        manager.clear_session()

    remove.assert_called_once_with(manager.session_file)


