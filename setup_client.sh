#!/bin/bash
echo "=== AdriaBOX Tenant Workspace Provisioning ==="
read -p "Enter the tenant identity name (e.g., sam, devil, max): " USERNAME

if [ -z "$USERNAME" ]; then
    echo "Error: Username cannot be empty."
    exit 1
fi

CONTAINER_NAME="adriabox-client-${USERNAME}"

echo "Deploying isolated target environment container: ${CONTAINER_NAME}..."
sudo docker run -d --name "$CONTAINER_NAME" \
  --network adriabox_adriabox-net \
  -e ADRIA_METADATA_URL="http://metadata:5000" \
  -v ~/AdriaBOX:/app \
  -w /app \
  python:3.12 tail -f /dev/null

echo "Bootstrapping Poetry driver within container context..."
sudo docker exec "$CONTAINER_NAME" pip install poetry

echo "Pruning dependency graph and assembling client-side packages..."
sudo docker exec "$CONTAINER_NAME" poetry install --without server

echo "=== Provisioning Complete. Dropping into interactive shell ==="
sudo docker exec -it "$CONTAINER_NAME" bash
