from metadata_server.server import AdriaServer


class FakeNodeRegistry:
    def __init__(self):
        self.nodes = []

    def register_storage_node(self, node_id, host, http_port, tcp_port, status="active", client_host="localhost"):
        node = {
            "node_id": node_id,
            "host": host,
            "client_host": client_host,
            "http_port": http_port,
            "tcp_port": tcp_port,
            "status": status,
            "last_seen": "test-time",
        }
        self.nodes = [existing for existing in self.nodes if existing["node_id"] != node_id]
        self.nodes.append(node)
        return node

    def list_storage_nodes(self):
        return sorted(self.nodes, key=lambda node: node["node_id"])

    def save_stored_file(self, **kwargs):
        return kwargs


def test_register_and_list_storage_nodes():
    server = AdriaServer(db=FakeNodeRegistry())
    client = server.app.test_client()

    response = client.post("/nodes", json={
        "node_id": "storage1",
        "host": "storage1",
        "http_port": 6001,
        "tcp_port": 7001,
    })

    assert response.status_code == 201
    assert response.get_json()["node_id"] == "storage1"

    response = client.get("/nodes")

    assert response.status_code == 200
    assert response.get_json()[0]["host"] == "storage1"


def test_register_storage_node_requires_required_fields():
    server = AdriaServer(db=FakeNodeRegistry())
    client = server.app.test_client()

    response = client.post("/nodes", json={"node_id": "storage1"})

    assert response.status_code == 400


def test_upload_plan_splits_file_across_three_nodes():
    db = FakeNodeRegistry()
    db.nodes = [
        {
            "node_id": "storage1",
            "host": "storage1",
            "client_host": "localhost",
            "http_port": 6001,
            "tcp_port": 7001,
            "status": "active",
            "last_seen": "test-time",
        },
        {
            "node_id": "storage2",
            "host": "storage2",
            "client_host": "localhost",
            "http_port": 6002,
            "tcp_port": 7002,
            "status": "active",
            "last_seen": "test-time",
        },
        {
            "node_id": "storage3",
            "host": "storage3",
            "client_host": "localhost",
            "http_port": 6003,
            "tcp_port": 7003,
            "status": "active",
            "last_seen": "test-time",
        },
    ]
    server = AdriaServer(db=db)
    client = server.app.test_client()

    response = client.post("/files/upload-plan", json={
        "filename": "demo.txt",
        "size": 300,
        "remote_dir": "/",
    })

    assert response.status_code == 200
    chunks = response.get_json()["chunks"]
    assert [chunk["node_id"] for chunk in chunks] == ["storage1", "storage2", "storage3"]
    assert [chunk["size"] for chunk in chunks] == [100, 100, 100]
