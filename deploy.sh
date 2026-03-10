#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ROOT_DIR}/.env.production"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.prod.yml"

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
else
    echo "ERROR: Docker Compose is required (docker compose plugin or docker-compose)." >&2
    exit 1
fi

echo "[1/8] Running production preflight checks..."
bash "${ROOT_DIR}/scripts/prod-preflight.sh"

echo "[2/8] Loading .env.production..."
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

echo "[3/8] Building and starting containers..."
"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

echo "[4/8] Restarting nginx to refresh backend upstream resolution..."
"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" restart nginx

echo "[5/8] Running database migrations and static collection..."
"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend python manage.py migrate
"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend python manage.py collectstatic --noinput

echo "[6/8] Running deployment security checks..."
"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend python manage.py check --deploy --tag security

echo "[7/8] Current service status:"
"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

echo "[8/8] Telegram webhook setup (optional)..."
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]]; then
    "${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend \
        python manage.py telegram_set_webhook --base-url "https://${DOMAIN}"
    "${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend \
        python manage.py telegram_check || true
else
    echo "Skipping Telegram webhook setup: TELEGRAM_BOT_TOKEN or TELEGRAM_WEBHOOK_SECRET not set."
fi

echo
echo "Deployment complete."
echo "Public endpoints:"
echo "  https://${DOMAIN}"
echo "  https://${DOMAIN}/api/docs/"
echo
echo "Useful commands:"
echo "  ${COMPOSE_CMD[*]} --env-file .env.production -f docker-compose.prod.yml logs -f backend"
echo "  ${COMPOSE_CMD[*]} --env-file .env.production -f docker-compose.prod.yml logs -f nginx"
