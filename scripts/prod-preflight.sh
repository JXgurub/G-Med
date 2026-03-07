#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.production"

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"
}

require_cmd docker

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  fail "Docker Compose is required (docker compose plugin or docker-compose)."
fi

[[ -f "$ENV_FILE" ]] || fail ".env.production not found at ${ENV_FILE}"
[[ -f "${ROOT_DIR}/docker-compose.prod.yml" ]] || fail "docker-compose.prod.yml not found"
[[ -f "${ROOT_DIR}/nginx.conf" ]] || fail "nginx.conf not found"
[[ -f "${ROOT_DIR}/ssl/cert.pem" ]] || fail "ssl/cert.pem not found"
[[ -f "${ROOT_DIR}/ssl/key.pem" ]] || fail "ssl/key.pem not found"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required_vars=(
  DJANGO_SECRET_KEY
  DB_NAME
  DB_USER
  DB_PASSWORD
  DOMAIN
  ALLOWED_HOSTS
  CORS_ALLOWED_ORIGINS
  CSRF_TRUSTED_ORIGINS
  FRONTEND_URL
  EMAIL_BACKEND
  EMAIL_HOST
  EMAIL_PORT
  EMAIL_USE_TLS
  DEFAULT_FROM_EMAIL
  ADMIN_URL
  CHANNEL_REDIS_URL
  HOSPITOLL_ADMIN_PASSWORD
  HOSPITOLL_APP_PASSWORD
)

for var_name in "${required_vars[@]}"; do
  value="${!var_name:-}"
  [[ -n "$value" ]] || fail "${var_name} is empty in .env.production"
done

if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -z "${TELEGRAM_WEBHOOK_SECRET:-}" ]]; then
  fail "TELEGRAM_WEBHOOK_SECRET is required when TELEGRAM_BOT_TOKEN is set"
fi

weak_markers=("change-this" "your-" "example" "localhost")
for marker in "${weak_markers[@]}"; do
  if grep -Eiq "${marker}" "$ENV_FILE"; then
    echo "WARNING: .env.production contains '${marker}'. Review production values." >&2
  fi
done

"${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "${ROOT_DIR}/docker-compose.prod.yml" config >/dev/null

echo "Preflight OK: production deployment prerequisites passed."
