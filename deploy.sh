#!/bin/bash
set -e

echo "🔄 Pulling latest image..."
docker-compose pull smartpay-api

echo "🚀 Restarting API container..."
docker-compose up -d --no-deps --build smartpay-api

echo "✅ Deployment complete."
