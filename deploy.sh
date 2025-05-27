#!/bin/bash
set -e

# -----------------------------
# CONFIG: Telegram
# -----------------------------
function notify_telegram() {
  local status="$1"
  local message="$2"
  local emoji
  if [ "$status" == "success" ]; then
    emoji="✅"
  else
    emoji="❌"
  fi

  curl -s -X POST https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage \
    -d chat_id=${TELEGRAM_CHAT_ID} \
    -d text="${emoji} *SmartPay Deployment ${status^}*\n${message}" \
    -d parse_mode=Markdown
}

# -----------------------------
# START DEPLOYMENT
# -----------------------------
echo "🚀 Starting SmartPay deployment..."

if [ -f ".env.prod" ]; then
  echo "📦 Loading environment from .env.prod"
  export $(grep -v '^#' .env.prod | xargs)
fi

trap 'notify_telegram "failure" "Deployment failed at step: $BASH_COMMAND"' ERR

echo "📥 Pulling latest code..."
git pull origin main

echo "🛑 Stopping running containers..."
docker-compose -f docker-compose.yml --env-file .env down

echo "🔧 Building fresh images..."
docker-compose -f docker-compose.yml --env-file .env build

echo "🗄️ Starting DB only..."
docker-compose -f docker-compose.yml --env-file .env up -d smartpay-postgres
sleep 5

echo "🧮 Running database migrations..."
docker-compose -f docker-compose.yml --env-file .env run smartpay-api alembic upgrade head

echo "⚙️ Starting all services..."
docker-compose -f docker-compose.yml --env-file .env up -d

notify_telegram "success" "Version deployed from branch \`$(git rev-parse --abbrev-ref HEAD)\` on host \`$(hostname)\`."

echo "✅ Deployment completed successfully."
