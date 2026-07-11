"""Tests for client-side chunk upload, download fallback, and deletion."""
from unittest.mock import Mock, call, mock_open, patch

import pytest

from client.transfer import AdriaTransferManager


def test_upload_file_chunks_sends_each_chunk_to_its_primary_pipeline():
    manager = AdriaTransferManager(request_timeout=3.0)
    plan_chunks = [
        {
            "index": 0,
            "offset": 0,
            "size": 100,
            "chunk_filename": "42_0_demo.bin.chunk",
            "primary_node": {
                "node_id": "node-a",
                "client_host": "storage-a",
                "tcp_port": 7001,
            },
            "pipeline": [
                {"node_id": "node-b", "host": "storage-b", "tcp_port": 7002}
            ],
        },
        {
            "index": 1,
            "offset": 100,
            "size": 50,
            "chunk_filename": "42_1_demo.bin.chunk",
            "primary_node": {
                "node_id": "node-b",
                "client_host": "storage-b",
                "tcp_port": 7002,
            },
            "pipeline": [
                {"node_id": "node-c", "host": "storage-c", "tcp_port": 7003}
            ],
        },
    ]
    source_open = mock_open(read_data=b"x" * 150)
    first_sender = Mock()
    first_sender.send_with_pipeline.return_value = True
    second_sender = Mock()
    second_sender.send_with_pipeline.return_value = True

    with (
        patch("builtins.open", source_open),
        patch(
            "client.transfer.ChunkStreamSender",
            side_effect=[first_sender, second_sender],
        ) as sender_cls,
    ):
        uploaded = manager.upload_file_chunks(
            "demo.bin",
            plan_chunks,
            "crypto-key",
            "1",
        )

    source = source_open()
    assert source.seek.call_args_list == [call(0), call(100)]
    assert sender_cls.call_args_list == [
        call("storage-a", 7001, timeout=3.0, crypto_key="crypto-key"),
        call("storage-b", 7002, timeout=3.0, crypto_key="crypto-key"),
    ]
    first_sender.send_with_pipeline.assert_called_once_with(
        source,
        "42_0_demo.bin.chunk",
        100,
        plan_chunks[0]["pipeline"],
        "1",
    )
    second_sender.send_with_pipeline.assert_called_once_with(
        source,
        "42_1_demo.bin.chunk",
        50,
        plan_chunks[1]["pipeline"],
        "1",
    )
    assert uploaded == [
        {
            "index": 0,
            "chunk_filename": "42_0_demo.bin.chunk",
            "node_id": "node-a",
            "size": 100,
        },
        {
            "index": 1,
            "chunk_filename": "42_1_demo.bin.chunk",
            "node_id": "node-b",
            "size": 50,
        },
    ]


def test_upload_file_chunks_raises_when_pipeline_replication_fails():
    manager = AdriaTransferManager(request_timeout=3.0)
    chunk = {
        "index": 4,
        "offset": 0,
        "size": 100,
        "chunk_filename": "42_4_demo.bin.chunk",
        "primary_node": {
            "node_id": "node-a",
            "client_host": "storage-a",
            "tcp_port": 7001,
        },
        "pipeline": [],
    }
    sender = Mock()
    sender.send_with_pipeline.return_value = False

    with (
        patch("builtins.open", mock_open(read_data=b"x" * 100)),
        patch("client.transfer.ChunkStreamSender", return_value=sender),
    ):
        with pytest.raises(
            Exception,
            match="Pipeline replication failed for chunk index 4",
        ):
            manager.upload_file_chunks("demo.bin", [chunk], "crypto-key", "1")


def test_download_file_chunks_falls_back_to_next_replica():
    manager = AdriaTransferManager(request_timeout=3.0)
    chunks = [
        {
            "index": 0,
            "size": 100,
            "chunk_filename": "42_0_demo.bin.chunk",
            "nodes": [
                {
                    "node_id": "node-a",
                    "client_host": "storage-a",
                    "tcp_port": 7001,
                },
                {
                    "node_id": "node-b",
                    "client_host": "storage-b",
                    "tcp_port": 7002,
                },
            ],
        }
    ]
    destination_open = mock_open()
    first_downloader = Mock()
    first_downloader.download.side_effect = ConnectionError("node offline")
    second_downloader = Mock()

    with (
        patch("builtins.open", destination_open),
        patch(
            "client.transfer.ChunkDownloader",
            side_effect=[first_downloader, second_downloader],
        ) as downloader_cls,
        patch("builtins.print") as print_mock,
    ):
        manager.download_file_chunks(
            "downloaded.bin",
            chunks,
            "crypto-key",
        )

    destination = destination_open()
    assert downloader_cls.call_args_list == [
        call("storage-a", 7001, timeout=3.0, crypto_key="crypto-key"),
        call("storage-b", 7002, timeout=3.0, crypto_key="crypto-key"),
    ]
    first_downloader.download.assert_called_once_with(
        "42_0_demo.bin.chunk",
        destination,
        100,
    )
    second_downloader.download.assert_called_once_with(
        "42_0_demo.bin.chunk",
        destination,
        100,
    )
    print_mock.assert_called_once()


def test_download_file_chunks_raises_when_all_replicas_fail():
    manager = AdriaTransferManager(request_timeout=3.0)
    chunks = [
        {
            "index": 2,
            "size": 50,
            "chunk_filename": "42_2_demo.bin.chunk",
            "nodes": [
                {
                    "node_id": "node-a",
                    "client_host": "storage-a",
                    "tcp_port": 7001,
                },
                {
                    "node_id": "node-b",
                    "client_host": "storage-b",
                    "tcp_port": 7002,
                },
            ],
        }
    ]
    first_downloader = Mock()
    first_downloader.download.side_effect = ConnectionError("first offline")
    second_downloader = Mock()
    second_downloader.download.side_effect = TimeoutError("second offline")

    with (
        patch("builtins.open", mock_open()),
        patch(
            "client.transfer.ChunkDownloader",
            side_effect=[first_downloader, second_downloader],
        ),
        patch("builtins.print"),
    ):
        with pytest.raises(
            Exception,
            match="Failed to retrieve chunk index 2.*second offline",
        ):
            manager.download_file_chunks(
                "downloaded.bin",
                chunks,
                "crypto-key",
            )


def test_download_file_chunks_raises_when_plan_has_no_replicas():
    manager = AdriaTransferManager(request_timeout=3.0)
    chunks = [
        {
            "index": 0,
            "size": 100,
            "chunk_filename": "42_0_demo.bin.chunk",
            "nodes": [],
        }
    ]

    with patch("builtins.open", mock_open()):
        with pytest.raises(
            Exception,
            match="All replicas are offline",
        ):
            manager.download_file_chunks(
                "downloaded.bin",
                chunks,
                "crypto-key",
            )


def test_purge_physical_chunks_deletes_all_reachable_targets():
    manager = AdriaTransferManager(request_timeout=3.0)
    chunks = [
        {
            "chunk_filename": "42_0_demo.bin.chunk",
            "client_host": "storage-a",
            "tcp_port": 7001,
        },
        {
            "chunk_filename": "42_0_demo.bin.chunk",
            "client_host": "storage-b",
            "tcp_port": 7002,
        },
    ]
    first_deleter = Mock()
    second_deleter = Mock()

    with patch(
        "client.transfer.ChunkDeleter",
        side_effect=[first_deleter, second_deleter],
    ) as deleter_cls:
        manager.purge_physical_chunks(chunks)

    assert deleter_cls.call_args_list == [
        call("storage-a", 7001, timeout=3.0),
        call("storage-b", 7002, timeout=3.0),
    ]
    first_deleter.delete.assert_called_once_with("42_0_demo.bin.chunk")
    second_deleter.delete.assert_called_once_with("42_0_demo.bin.chunk")


def test_purge_physical_chunks_ignores_unreachable_node():
    manager = AdriaTransferManager(request_timeout=3.0)
    chunks = [
        {
            "chunk_filename": "42_0_demo.bin.chunk",
            "client_host": "storage-a",
            "tcp_port": 7001,
        },
        {
            "chunk_filename": "42_0_demo.bin.chunk",
            "client_host": "storage-b",
            "tcp_port": 7002,
        },
    ]
    first_deleter = Mock()
    first_deleter.delete.side_effect = ConnectionError("node offline")
    second_deleter = Mock()

    with patch(
        "client.transfer.ChunkDeleter",
        side_effect=[first_deleter, second_deleter],
    ):
        manager.purge_physical_chunks(chunks)

    first_deleter.delete.assert_called_once_with("42_0_demo.bin.chunk")
    second_deleter.delete.assert_called_once_with("42_0_demo.bin.chunk")
