#!/bin/bash
echo "=== AdriaBOX Infrastructure Automation ==="
echo "Generating secure cryptographic 256-bit JWT secret key..."
JWT_KEY=$(openssl rand -hex 32)

echo "Provisioning .env configuration framework..."
cat <<EOT > .env
ADRIABOX_ENV=production
METADATA_SERVER_HOST=0.0.0.0
METADATA_SERVER_PORT=5000
JWT_SECRET_KEY=${JWT_KEY}
JWT_EXPIRATION_HOURS=24
STORAGE_BIND_ADDRESS=0.0.0.0
STORAGE_INTERNAL_PORT=5001
REPLICATION_FACTOR=3
TOTAL_STORAGE_NODES=12
EOT

echo "Compiling system images and launching decentralized fleet..."
sudo docker-compose up --build -d

echo "=== Cluster Core Infrastructure Online ==="
