import socket
import threading

import pytest

from common.tcp import ACK_ERROR, ACK_OK, create_server_socket, handle_connection, send_bytes


def _start_one_shot_storage(tmp_path):
    server = create_server_socket("127.0.0.1", 0)
    host, port = server.getsockname()

    def serve_once():
        try:
            conn, _ = server.accept()
            handle_connection(conn, str(tmp_path))
        finally:
            server.close()

    thread = threading.Thread(target=serve_once, daemon=True)
    thread.start()
    return host, port, thread


def test_send_bytes_waits_for_storage_ack_after_writing_file(tmp_path):
    host, port, thread = _start_one_shot_storage(tmp_path)

    send_bytes(host, port, "demo.chunk0", b"hello world")
    thread.join(timeout=2)

    assert (tmp_path / "demo.chunk0").read_bytes() == b"hello world"
    assert not thread.is_alive()


def test_send_bytes_raises_when_storage_does_not_confirm():
    server = create_server_socket("127.0.0.1", 0)
    host, port = server.getsockname()

    def reject_once():
        try:
            conn, _ = server.accept()
            with conn:
                conn.sendall(ACK_ERROR)
        finally:
            server.close()

    thread = threading.Thread(target=reject_once, daemon=True)
    thread.start()

    with pytest.raises(ConnectionError):
        send_bytes(host, port, "demo.chunk0", b"hello world")

    thread.join(timeout=2)


def test_handle_connection_sends_ok_only_after_complete_payload(tmp_path):
    server_sock, client_sock = socket.socketpair()

    try:
        thread = threading.Thread(
            target=handle_connection,
            args=(server_sock, str(tmp_path)),
            daemon=True,
        )
        thread.start()

        name = b"complete.chunk"
        payload = b"abc123"
        client_sock.sendall(
            len(name).to_bytes(4, "big")
            + name
            + len(payload).to_bytes(8, "big")
            + payload
        )
        client_sock.shutdown(socket.SHUT_WR)

        assert client_sock.recv(len(ACK_OK)) == ACK_OK
        thread.join(timeout=2)
        assert (tmp_path / "complete.chunk").read_bytes() == payload
    finally:
        client_sock.close()
