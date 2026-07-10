"""Tests for the low-level TCP client protocol helpers."""
import io
import json
import struct
from unittest.mock import Mock, call, patch

import pytest

from common.tcp import (
    AdriaTCPStreamer,
    ChunkDeleter,
    ChunkDownloader,
    ChunkStreamSender,
    FileReceiver,
)


def test_recv_exact_combines_fragmented_packets():
    sock = Mock()
    sock.recv.side_effect = [b"ab", b"cd", b"ef"]

    result = AdriaTCPStreamer()._recv_exact(sock, 6)

    assert result == bytearray(b"abcdef")
    assert sock.recv.call_args_list == [call(6), call(4), call(2)]


def test_recv_exact_returns_none_when_connection_closes_early():
    sock = Mock()
    sock.recv.side_effect = [b"ab", b""]

    assert AdriaTCPStreamer()._recv_exact(sock, 4) is None


def test_chunk_sender_sends_header_payload_and_accepts_ack():
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.recv.return_value = AdriaTCPStreamer.ACK_OK
    source = io.BytesIO(b"hello")

    with patch("common.tcp.socket.create_connection", return_value=connection):
        success = ChunkStreamSender("storage-a", 7001, timeout=3.0).send_with_pipeline(
            source,
            "demo.chunk",
            5,
            [{"node_id": "node-b", "host": "storage-b", "tcp_port": 7002}],
        )

    header = connection.sendall.call_args_list[0].args[0]
    assert header[:1] == b"U"
    metadata_length, chunk_size = struct.unpack(">II", header[1:9])
    metadata = json.loads(header[9:9 + metadata_length].decode("utf-8"))
    assert chunk_size == 5
    assert metadata["chunk_filename"] == "demo.chunk"
    assert connection.sendall.call_args_list[1] == call(b"hello")
    assert success is True


def test_chunk_sender_returns_false_for_error_ack():
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.recv.return_value = AdriaTCPStreamer.ACK_ERROR

    with patch("common.tcp.socket.create_connection", return_value=connection):
        result = ChunkStreamSender("storage-a", 7001).send_with_pipeline(
            io.BytesIO(b"data"),
            "demo.chunk",
            4,
            [],
        )

    assert result is False


def test_chunk_downloader_requests_file_and_writes_payload():
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.recv.side_effect = [b"abc", b"def"]
    destination = io.BytesIO()

    with patch("common.tcp.socket.create_connection", return_value=connection):
        ChunkDownloader("storage-a", 7001, timeout=3.0).download(
            "demo.chunk",
            destination,
            6,
        )

    filename = b"demo.chunk"
    connection.sendall.assert_called_once_with(
        b"D" + struct.pack(">I", len(filename)) + filename
    )
    assert destination.getvalue() == b"abcdef"


def test_chunk_downloader_raises_when_connection_closes_midway():
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    connection.recv.side_effect = [b"abc", b""]

    with patch("common.tcp.socket.create_connection", return_value=connection):
        with pytest.raises(IOError, match="Connection severed"):
            ChunkDownloader("storage-a", 7001).download(
                "demo.chunk",
                io.BytesIO(),
                6,
            )


def test_chunk_deleter_sends_delete_header():
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)

    with patch("common.tcp.socket.create_connection", return_value=connection):
        ChunkDeleter("storage-a", 7001, timeout=3.0).delete("demo.chunk")

    filename = b"demo.chunk"
    connection.sendall.assert_called_once_with(
        b"X" + struct.pack(">I", len(filename)) + filename
    )


@pytest.mark.parametrize(
    ("command", "handler_name"),
    [
        (b"U", "handle_pipeline_upload"),
        (b"D", "handle_download"),
        (b"X", "handle_delete"),
    ],
)
def test_file_receiver_dispatches_known_commands(command, handler_name):
    connection = Mock()
    receiver = FileReceiver(connection, "storage")

    with (
        patch.object(receiver, "_recv_exact", return_value=command),
        patch.object(receiver, handler_name) as handler,
    ):
        receiver.serve()

    handler.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_file_receiver_rejects_unknown_command():
    connection = Mock()
    receiver = FileReceiver(connection, "storage")

    with patch.object(receiver, "_recv_exact", return_value=b"?"):
        receiver.serve()

    connection.sendall.assert_called_once_with(AdriaTCPStreamer.ACK_ERROR)
    connection.close.assert_called_once_with()
