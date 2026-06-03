"""Data Transfer component handling raw TCP chunk streams and client-side failover."""
import os
from common.tcp import ChunkStreamSender, ChunkDownloader, ChunkDeleter

class AdriaTransferManager:
    def __init__(self, request_timeout: float):
        self.timeout = request_timeout

    def upload_file_chunks(self, local_filepath: str, plan_chunks: list, crypto_key: str) -> list:
        """Slice the local file and push chunks into their designated replication pipelines."""
        uploaded_chunks = []
        with open(local_filepath, "rb") as source:
            for chunk in plan_chunks:
                source.seek(chunk["offset"])
                primary = chunk["primary_node"]
                pipeline_targets = chunk["pipeline"]

                sender = ChunkStreamSender(
                    primary["client_host"], 
                    int(primary["tcp_port"]), 
                    timeout=self.timeout, 
                    crypto_key=crypto_key
                )
                
                success = sender.send_with_pipeline(
                    source, chunk["chunk_filename"], chunk["size"], pipeline_targets
                )
                if not success:
                    raise Exception(f"Pipeline replication failed for chunk index {chunk['index']}")

                uploaded_chunks.append({
                    "index": chunk["index"],
                    "chunk_filename": chunk["chunk_filename"],
                    "node_id": primary["node_id"],
                    "size": chunk["size"]
                })
        return uploaded_chunks

    def download_file_chunks(self, local_destination: str, plan_chunks: list, crypto_key: str):
        """Download file blocks sequentially, orchestrating a fallback loop through replicas if nodes fail."""
        with open(local_destination, "wb") as dest_file:
            for chunk in plan_chunks:
                chunk_success = False
                last_error = None
                
                for node in chunk.get("nodes", []):
                    try:
                        downloader = ChunkDownloader(
                            node["client_host"], 
                            int(node["tcp_port"]), 
                            timeout=self.timeout, 
                            crypto_key=crypto_key
                        )
                        downloader.download(chunk["chunk_filename"], dest_file, chunk["size"])
                        chunk_success = True
                        break
                    except Exception as e:
                        last_error = e
                        print(f"\n[Warning] Node {node['node_id']} unreachable for chunk {chunk['index']}. Threat mitigated, trying replica...")
                
                if not chunk_success:
                    raise Exception(f"Critical: Failed to retrieve chunk index {chunk['index']}. All replicas are offline. Last error: {last_error}")

    def purge_physical_chunks(self, plan_chunks: list):
        """Broadcast a best-effort asynchronous erasure command to wipe orphan blocks from target nodes."""
        for chunk in plan_chunks:
            try:
                ChunkDeleter(chunk["client_host"], int(chunk["tcp_port"]), timeout=self.timeout).delete(chunk["chunk_filename"])
            except Exception:
                pass

