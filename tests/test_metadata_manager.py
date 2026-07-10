"""Tests for metadata plan generation and authorization helpers."""
from unittest.mock import Mock, patch

import jwt
import pytest

from common.constants import LOGICAL_BLOCK_SIZE
from metadata_server.manager import AdriaMetadataManager, SECRET_KEY


STORAGE_NODES_CFG = (
    "node-a:internal-a:7001:client-a:8001,"
    "node-b:internal-b:7002:client-b:8002,"
    "node-c:internal-c:7003:client-c:8003"
)


def make_manager():
    with patch("metadata_server.manager.DatabaseManager") as db_cls:
        db = Mock()
        db_cls.return_value = db
        manager = AdriaMetadataManager("ignored.db", STORAGE_NODES_CFG)

    return manager, db


def test_parse_storage_nodes_reads_internal_and_client_addresses():
    manager, _ = make_manager()

    assert manager.storage_nodes == [
        {
            "node_id": "node-a",
            "host": "internal-a",
            "tcp_port": 7001,
            "client_host": "client-a",
            "client_tcp_port": 8001,
        },
        {
            "node_id": "node-b",
            "host": "internal-b",
            "tcp_port": 7002,
            "client_host": "client-b",
            "client_tcp_port": 8002,
        },
        {
            "node_id": "node-c",
            "host": "internal-c",
            "tcp_port": 7003,
            "client_host": "client-c",
            "client_tcp_port": 8003,
        },
    ]


def test_build_upload_plan_requires_at_least_three_storage_nodes():
    manager, _ = make_manager()
    manager.storage_nodes = manager.storage_nodes[:2]

    with pytest.raises(RuntimeError, match="At least 3 nodes required"):
        manager.build_upload_plan(
            {"user_id": 10, "role": "user"},
            "demo.txt",
            100,
            "/docs",
        )


def test_build_upload_plan_creates_chunk_pipeline_and_records_file():
    manager, db = make_manager()
    db.add_file.return_value = 42

    plan = manager.build_upload_plan(
        {"user_id": 10, "role": "user"},
        "demo.txt",
        LOGICAL_BLOCK_SIZE + 5,
        "docs",
    )

    db.add_file.assert_called_once_with(
        "/docs/demo.txt",
        LOGICAL_BLOCK_SIZE + 5,
        2,
        owner_id=10,
    )
    assert plan["file_id"] == 42
    assert plan["remote_path"] == "/docs/demo.txt"
    assert [chunk["offset"] for chunk in plan["chunks"]] == [0, LOGICAL_BLOCK_SIZE]
    assert [chunk["size"] for chunk in plan["chunks"]] == [LOGICAL_BLOCK_SIZE, 5]
    assert plan["chunks"][0]["primary_node"]["node_id"] == "node-a"
    assert [node["node_id"] for node in plan["chunks"][0]["pipeline"]] == [
        "node-b",
        "node-c",
    ]
    assert plan["chunks"][1]["primary_node"]["node_id"] == "node-b"
    assert [node["node_id"] for node in plan["chunks"][1]["pipeline"]] == [
        "node-c",
        "node-a",
    ]


def test_build_upload_plan_handles_empty_file_with_zero_sized_chunk():
    manager, db = make_manager()
    db.add_file.return_value = 7

    plan = manager.build_upload_plan(
        {"user_id": 10, "role": "user"},
        "empty.txt",
        0,
        "/",
    )

    db.add_file.assert_called_once_with("/empty.txt", 0, 1, owner_id=10)
    assert len(plan["chunks"]) == 1
    assert plan["chunks"][0]["size"] == 0
    assert plan["chunks"][0]["offset"] == 0


def test_build_download_plan_returns_replicas_for_owner():
    manager, db = make_manager()
    db.get_file_by_name.return_value = {
        "id": 42,
        "filename": "/demo.txt",
        "size": 100,
        "owner_id": 10,
    }
    db.get_chunks_by_file_id.return_value = [
        {"chunk_index": 0, "chunk_filename": "42_0_demo.txt.chunk", "size": 100}
    ]

    plan = manager.build_download_plan(
        {"user_id": 10, "role": "user"},
        "demo.txt",
    )

    db.get_file_by_name.assert_called_once_with("/demo.txt")
    assert plan["file_id"] == 42
    assert plan["filename"] == "/demo.txt"
    assert plan["size"] == 100
    assert [node["node_id"] for node in plan["chunks"][0]["nodes"]] == [
        "node-a",
        "node-b",
        "node-c",
    ]


def test_build_download_plan_allows_admin_to_access_other_user_file():
    manager, db = make_manager()
    db.get_file_by_name.return_value = {
        "id": 42,
        "filename": "/demo.txt",
        "size": 100,
        "owner_id": 10,
    }
    db.get_chunks_by_file_id.return_value = []

    plan = manager.build_download_plan(
        {"user_id": 99, "role": "admin"},
        "/demo.txt",
    )

    assert plan["file_id"] == 42


@pytest.mark.parametrize(
    "file_info",
    [
        None,
        {"id": 42, "filename": "/demo.txt", "size": 100, "owner_id": 10},
    ],
)
def test_build_download_plan_hides_missing_and_unauthorized_files(file_info):
    manager, db = make_manager()
    db.get_file_by_name.return_value = file_info

    with pytest.raises(FileNotFoundError, match="File not found"):
        manager.build_download_plan(
            {"user_id": 99, "role": "user"},
            "/demo.txt",
        )


def test_commit_file_chunks_persists_each_chunk_mapping():
    manager, db = make_manager()

    manager.commit_file_chunks(
        42,
        [
            {
                "index": 0,
                "node_id": "node-a",
                "chunk_filename": "42_0_demo.txt.chunk",
                "size": 100,
            },
            {
                "index": 1,
                "node_id": "node-b",
                "chunk_filename": "42_1_demo.txt.chunk",
                "size": 50,
            },
        ],
    )

    assert db.add_chunk.call_args_list[0].args == (
        42,
        0,
        "node-a",
        "42_0_demo.txt.chunk",
        100,
    )
    assert db.add_chunk.call_args_list[1].args == (
        42,
        1,
        "node-b",
        "42_1_demo.txt.chunk",
        50,
    )


def test_get_file_deletion_plan_targets_all_replicas_for_each_chunk():
    manager, db = make_manager()
    db.get_chunks_by_file_id.return_value = [
        {"chunk_index": 1, "chunk_filename": "42_1_demo.txt.chunk"}
    ]

    targets = manager.get_file_deletion_plan(42)

    assert targets == [
        {
            "chunk_filename": "42_1_demo.txt.chunk",
            "client_host": "client-b",
            "tcp_port": 8002,
        },
        {
            "chunk_filename": "42_1_demo.txt.chunk",
            "client_host": "client-c",
            "tcp_port": 8003,
        },
        {
            "chunk_filename": "42_1_demo.txt.chunk",
            "client_host": "client-a",
            "tcp_port": 8001,
        },
    ]


def test_generate_token_contains_user_identity_and_role():
    manager, db = make_manager()
    db.get_user_by_username.return_value = {
        "id": 10,
        "username": "mario",
        "role": "admin",
    }

    token = manager.generate_token("mario")
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

    assert payload["user_id"] == 10
    assert payload["username"] == "mario"
    assert payload["role"] == "admin"


def test_authorize_request_rejects_missing_bearer_token():
    manager, _ = make_manager()

    with pytest.raises(PermissionError, match="Missing or malformed"):
        manager.authorize_request(None)
