# 📦 AdriaBOX

## 🚀 Vision

AdriaBOX is a decentralized storage system designed as a distributed matrix with dynamic replication and fault-tolerant architecture.

The system is composed of:
- **Metadata Server** → acts as controller and directory
- **Storage Nodes** → handle physical storage and replication of file chunks

The Metadata Server is responsible for:
- File tracking
- Node coordination
- Load balancing

Storage Nodes are responsible for:
- Chunk storage
- Data replication
- Serving client requests

### ⚠️ Architectural Note

The Metadata Server is a **Single Point of Failure (SPOF)**.

To mitigate this (within project scope):
- Its state is persisted in a **SQL database**
- Fast recovery is ensured upon restart

Future improvements:
- Multi-orchestrator architecture
- Consensus algorithms (e.g., Raft, Paxos) will be **theoretically analyzed and documented**

---

## 🎯 Learning Goals

This project explores key distributed systems concepts:

### 📌 CAP Theorem Trade-offs
- Balance between **Consistency** and **Availability**
- Behavior under network partitions

### 🔁 Replication & Fault Tolerance
- Data redundancy across nodes
- System resilience to node failures

### 🧠 SPOF Awareness & State Persistence
- Managing orchestrator reliability
- Introducing the **consensus problem**

### 🌐 Low-Level Networking
- Custom protocols using **TCP sockets**
- Binary data transfer

### ⚖️ Workload Distribution
- Load balancing across storage nodes
- Efficient resource utilization

### 🐳 Containerization & Orchestration
- Deployment using **Docker**
- Simulation of failures and scaling via **Docker Compose**

---

## 🛠️ Technologies

### Programming Language
- Python (Client, Metadata Server, Storage Nodes)

### Networking
- TCP Sockets → data transfer
- REST APIs → metadata queries

### Database
- SQL → Metadata persistence

### Infrastructure
- Docker
- Docker Compose

### Modeling
- PlantUML → architecture & sequence diagrams

---

## 📦 System Components

### 🖥️ Client (CLI)
- Upload/download files
- Interact with Metadata Server

### 🧭 Metadata Server
- Maintains file index
- Tracks storage nodes
- Handles load balancing
- Coordinates replication

### 💾 Storage Nodes
- Store file chunks
- Replicate data
- Serve read/write operations

---

## 📚 Usage Scenario

1. A user uploads a file via the CLI
2. The Metadata Server:
   - Splits the file into chunks
   - Distributes chunks across storage nodes
   - Creates replicas dynamically
3. Storage Nodes store and replicate data
4. If a node fails:
   - Data is still available from replicas
5. The user retrieves the file seamlessly

---

## 🐳 Deployment

The system is designed to run using Docker Compose:

```bash
docker-compose up --build
