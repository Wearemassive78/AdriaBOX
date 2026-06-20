"""Tests for storage node connection handling and server startup."""
from unittest.mock import Mock, patch

from storage_node.node import handle_client_connection, main


def test_handle_client_connection_delegates_to_file_receiver():
    connection = Mock()

    with patch("storage_node.node.FileReceiver") as receiver_cls:
        receiver = Mock()
        receiver_cls.return_value = receiver

        handle_client_connection(connection, "storage/node-a")

    receiver_cls.assert_called_once_with(connection, "storage/node-a")
    receiver.serve.assert_called_once_with()


def test_main_configures_socket_and_starts_daemon_thread():
    server_socket = Mock()
    connection = Mock()
    address = ("127.0.0.1", 50000)
    server_socket.accept.side_effect = [
        (connection, address),
        RuntimeError("stop test server"),
    ]

    client_thread = Mock()

    with (
        patch(
            "storage_node.node.argparse.ArgumentParser.parse_args",
            return_value=Mock(
                host="127.0.0.1",
                tcp_port=7001,
                storage_dir="storage/node-a",
            ),
        ),
        patch("storage_node.node.os.makedirs") as makedirs,
        patch("storage_node.node.socket.socket", return_value=server_socket) as socket_cls,
        patch("storage_node.node.threading.Thread", return_value=client_thread) as thread_cls,
        patch("builtins.print") as print_mock,
    ):
        main()

    makedirs.assert_called_once_with("storage/node-a", exist_ok=True)
    socket_cls.assert_called_once()
    server_socket.setsockopt.assert_called_once()
    server_socket.bind.assert_called_once_with(("127.0.0.1", 7001))
    server_socket.listen.assert_called_once_with(128)
    thread_cls.assert_called_once_with(
        target=handle_client_connection,
        args=(connection, "storage/node-a"),
        daemon=True,
    )
    client_thread.start.assert_called_once_with()
    server_socket.close.assert_called_once_with()
    print_mock.assert_any_call(
        "[Active] AdriaBOX Storage Server listening on TCP interface "
        "127.0.0.1:7001"
    )
    print_mock.assert_any_call(
        "[Critical Fault] Storage server engine crashed unexpectedly: "
        "stop test server"
    )


def test_main_closes_socket_when_bind_fails():
    server_socket = Mock()
    server_socket.bind.side_effect = OSError("address already in use")

    with (
        patch(
            "storage_node.node.argparse.ArgumentParser.parse_args",
            return_value=Mock(
                host="0.0.0.0",
                tcp_port=7001,
                storage_dir="storage/node-a",
            ),
        ),
        patch("storage_node.node.os.makedirs"),
        patch("storage_node.node.socket.socket", return_value=server_socket),
        patch("storage_node.node.threading.Thread") as thread_cls,
        patch("builtins.print") as print_mock,
    ):
        main()

    server_socket.listen.assert_not_called()
    thread_cls.assert_not_called()
    server_socket.close.assert_called_once_with()
    print_mock.assert_called_once_with(
        "[Critical Fault] Storage server engine crashed unexpectedly: "
        "address already in use"
    )


def test_main_uses_default_host_when_not_provided():
    server_socket = Mock()
    server_socket.accept.side_effect = RuntimeError("stop test server")

    with (
        patch(
            "storage_node.node.argparse.ArgumentParser.parse_args",
            return_value=Mock(
                host="0.0.0.0",
                tcp_port=7002,
                storage_dir="storage/node-b",
            ),
        ),
        patch("storage_node.node.os.makedirs"),
        patch("storage_node.node.socket.socket", return_value=server_socket),
        patch("builtins.print"),
    ):
        main()

    server_socket.bind.assert_called_once_with(("0.0.0.0", 7002))
    server_socket.close.assert_called_once_with()
