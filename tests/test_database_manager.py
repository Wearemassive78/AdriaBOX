"""Tests for SQLite persistence in the metadata database manager."""
import sqlite3

import pytest

from metadata_server.db import DatabaseManager


class InMemoryDatabaseManager(DatabaseManager):
    def __init__(self):
        self.db_path = ":memory:"
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self):
        return self.connection


@pytest.fixture
def database():
    manager = InMemoryDatabaseManager()

    yield manager

    manager.connection.close()


def test_register_and_verify_user(database):
    user_id = database.register_user("mario", "password123")

    user = database.verify_user("mario", "password123")

    assert user == {
        "id": user_id,
        "username": "mario",
        "role": "user",
    }


def test_register_user_rejects_duplicate_username(database):
    database.register_user("mario", "password123")

    with pytest.raises(ValueError, match="Username already exists"):
        database.register_user("mario", "another-password")


def test_verify_user_rejects_wrong_password(database):
    database.register_user("mario", "password123")

    assert database.verify_user("mario", "wrong-password") is None


def test_get_user_by_username_returns_identity_and_role(database):
    user_id = database.register_user("admin", "password123", role="admin")

    assert database.get_user_by_username("admin") == {
        "id": user_id,
        "username": "admin",
        "role": "admin",
    }


def test_add_file_and_chunks_can_be_retrieved_in_index_order(database):
    user_id = database.register_user("mario", "password123")
    file_id = database.add_file(
        "/docs/demo.txt",
        size=150,
        chunks=2,
        owner_id=user_id,
    )

    database.add_chunk(file_id, 1, "node-b", "demo.chunk1", 50)
    database.add_chunk(file_id, 0, "node-a", "demo.chunk0", 100)

    file_info = database.get_file_by_name("/docs/demo.txt")
    chunks = database.get_chunks_by_file_id(file_id)

    assert file_info["id"] == file_id
    assert file_info["owner_id"] == user_id
    assert file_info["size"] == 150
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]
    assert [chunk["chunk_filename"] for chunk in chunks] == [
        "demo.chunk0",
        "demo.chunk1",
    ]


def test_list_files_in_directory_groups_nested_paths(database):
    user_id = database.register_user("mario", "password123")
    database.add_file("/notes.txt", 10, 1, user_id)
    database.add_file("/docs/report.pdf", 20, 1, user_id)
    database.add_file("/docs/archive/old.pdf", 30, 1, user_id)

    root_entries = database.list_files_in_dir("/", user_id, "user")
    docs_entries = database.list_files_in_dir("/docs", user_id, "user")

    assert root_entries == [
        {"filename": "notes.txt", "is_dir": False, "size": 10, "chunks": 1},
        {"filename": "docs", "is_dir": True, "size": 0, "chunks": 0},
    ]
    assert docs_entries == [
        {"filename": "report.pdf", "is_dir": False, "size": 20, "chunks": 1},
        {"filename": "archive", "is_dir": True, "size": 0, "chunks": 0},
    ]


def test_regular_user_only_lists_owned_files_while_admin_lists_all(database):
    mario_id = database.register_user("mario", "password123")
    luigi_id = database.register_user("luigi", "password123")
    database.add_file("/mario.txt", 10, 1, mario_id)
    database.add_file("/luigi.txt", 20, 1, luigi_id)

    mario_files = database.list_files_in_dir("/", mario_id, "user")
    admin_files = database.list_files_in_dir("/", mario_id, "admin")

    assert [entry["filename"] for entry in mario_files] == ["mario.txt"]
    assert {entry["filename"] for entry in admin_files} == {
        "mario.txt",
        "luigi.txt",
    }


def test_get_user_quota_sums_owned_file_sizes(database):
    user_id = database.register_user("mario", "password123")
    database.add_file("/first.bin", 100, 1, user_id)
    database.add_file("/second.bin", 250, 1, user_id)

    assert database.get_user_quota(user_id) == 350


def test_delete_file_removes_metadata_and_chunks(database):
    user_id = database.register_user("mario", "password123")
    file_id = database.add_file("/demo.txt", 100, 1, user_id)
    database.add_chunk(file_id, 0, "node-a", "demo.chunk0", 100)

    database.delete_file(file_id)

    assert database.get_file_by_name("/demo.txt") is None
    assert database.get_chunks_by_file_id(file_id) == []


def test_delete_user_and_metadata_removes_all_owned_records(database):
    user_id = database.register_user("mario", "password123")
    file_id = database.add_file("/demo.txt", 100, 1, user_id)
    database.add_chunk(file_id, 0, "node-a", "demo.chunk0", 100)

    database.delete_user_and_metadata(user_id)

    assert database.get_user_by_username("mario") is None
    assert database.get_file_by_name("/demo.txt") is None
    assert database.get_chunks_by_file_id(file_id) == []


def test_get_all_users_with_usage_reports_zero_and_accumulated_usage(database):
    mario_id = database.register_user("mario", "password123")
    database.register_user("luigi", "password123")
    database.add_file("/first.bin", 100, 1, mario_id)
    database.add_file("/second.bin", 50, 1, mario_id)

    users = database.get_all_users_with_usage()
    by_username = {user["username"]: user for user in users}

    assert by_username["mario"]["total_used"] == 150
    assert by_username["luigi"]["total_used"] == 0
