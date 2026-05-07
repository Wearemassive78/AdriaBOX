from metadata_server.server import AdriaServer


class FakeNodeRegistry:
    def __init__(self):
        self.nodes = []

    def register_storage_node(self, node_id, host, http_port, tcp_port, status="active"):
        node = {
            "node_id": node_id,
            "host": host,
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
