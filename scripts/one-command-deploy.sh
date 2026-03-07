#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_TEMPLATE="${ROOT_DIR}/.env.production.example"
ENV_FILE="${ROOT_DIR}/.env.production"
SSL_DIR="${ROOT_DIR}/ssl"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.prod.yml"

DOMAIN=""
CERTBOT_EMAIL=""
EMAIL_HOST_PASSWORD="${EMAIL_HOST_PASSWORD:-}"
EMAIL_HOST_USER="${EMAIL_HOST_USER:-}"
DEFAULT_FROM_EMAIL="${DEFAULT_FROM_EMAIL:-}"
SERVER_EMAIL="${SERVER_EMAIL:-}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_BOT_USERNAME="${TELEGRAM_BOT_USERNAME:-hosptol_bot}"

SKIP_BOOTSTRAP=0
SELF_SIGNED_SSL=0

usage() {
  cat <<'EOF'
One-command production deploy for Hetzner/Ubuntu.

Usage:
  bash scripts/one-command-deploy.sh \
    --domain g-med.uz \
    --certbot-email mailer@g-med.uz \
    --email-host-password '<smtp-app-password>' \
    [--email-host-user mailer@g-med.uz] \
    [--default-from-email noreply@g-med.uz] \
    [--server-email noreply@g-med.uz] \
    [--telegram-bot-token '<bot-token>'] \
    [--telegram-bot-username hosptol_bot] \
    [--skip-bootstrap] \
    [--self-signed-ssl]

Notes:
- --self-signed-ssl skips Certbot and creates a temporary self-signed cert.
- If --email-host-password is omitted, the script prompts for it securely.
- Run from project root or anywhere inside the repository.
EOF
}

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"
}

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

run_root() {
  if [[ -n "$SUDO" ]]; then
    $SUDO "$@"
  else
    "$@"
  fi
}

set_env_var() {
  local key="$1"
  local value="$2"
  local escaped

  escaped="${value//\\/\\\\}"
  escaped="${escaped//&/\\&}"
  escaped="${escaped//|/\\|}"

  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
  else
    printf "%s=%s\n" "$key" "$value" >> "$ENV_FILE"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --certbot-email)
      CERTBOT_EMAIL="$2"
      shift 2
      ;;
    --email-host-password)
      EMAIL_HOST_PASSWORD="$2"
      shift 2
      ;;
    --email-host-user)
      EMAIL_HOST_USER="$2"
      shift 2
      ;;
    --default-from-email)
      DEFAULT_FROM_EMAIL="$2"
      shift 2
      ;;
    --server-email)
      SERVER_EMAIL="$2"
      shift 2
      ;;
    --telegram-bot-token)
      TELEGRAM_BOT_TOKEN="$2"
      shift 2
      ;;
    --telegram-bot-username)
      TELEGRAM_BOT_USERNAME="$2"
      shift 2
      ;;
    --skip-bootstrap)
      SKIP_BOOTSTRAP=1
      shift
      ;;
    --self-signed-ssl)
      SELF_SIGNED_SSL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
done

[[ -n "$DOMAIN" ]] || fail "--domain is required"
[[ -f "$ENV_TEMPLATE" ]] || fail ".env.production.example not found"
[[ -f "$COMPOSE_FILE" ]] || fail "docker-compose.prod.yml not found"

if [[ "$SELF_SIGNED_SSL" -eq 0 ]]; then
  [[ -n "$CERTBOT_EMAIL" ]] || fail "--certbot-email is required unless --self-signed-ssl is used"
fi

if [[ -z "$EMAIL_HOST_PASSWORD" ]]; then
  read -rsp "Enter EMAIL_HOST_PASSWORD: " EMAIL_HOST_PASSWORD
  echo
fi
[[ -n "$EMAIL_HOST_PASSWORD" ]] || fail "EMAIL_HOST_PASSWORD cannot be empty"

if [[ -z "$EMAIL_HOST_USER" ]]; then
  EMAIL_HOST_USER="mailer@${DOMAIN}"
fi
if [[ -z "$DEFAULT_FROM_EMAIL" ]]; then
  DEFAULT_FROM_EMAIL="noreply@${DOMAIN}"
fi
if [[ -z "$SERVER_EMAIL" ]]; then
  SERVER_EMAIL="noreply@${DOMAIN}"
fi

require_cmd openssl
require_cmd grep
require_cmd sed

cd "$ROOT_DIR"

if [[ "$SKIP_BOOTSTRAP" -eq 0 ]]; then
  echo "[0/6] Running server bootstrap..."
  bash "${ROOT_DIR}/scripts/hetzner-bootstrap.sh"
else
  echo "[0/6] Skipping bootstrap (--skip-bootstrap provided)."
fi

echo "[1/6] Preparing .env.production..."
cp "$ENV_TEMPLATE" "$ENV_FILE"

DJANGO_SECRET_KEY="$(openssl rand -base64 64 | tr -d '\n')"
DB_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
HOSPITOLL_ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
HOSPITOLL_APP_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
TELEGRAM_WEBHOOK_SECRET="$(openssl rand -hex 32)"

set_env_var "DJANGO_SECRET_KEY" "$DJANGO_SECRET_KEY"
set_env_var "DB_PASSWORD" "$DB_PASSWORD"
set_env_var "HOSPITOLL_ADMIN_PASSWORD" "$HOSPITOLL_ADMIN_PASSWORD"
set_env_var "HOSPITOLL_APP_PASSWORD" "$HOSPITOLL_APP_PASSWORD"
set_env_var "DOMAIN" "$DOMAIN"
set_env_var "ALLOWED_HOSTS" "$DOMAIN,www.${DOMAIN}"
set_env_var "CORS_ALLOWED_ORIGINS" "https://${DOMAIN},https://www.${DOMAIN}"
set_env_var "CSRF_TRUSTED_ORIGINS" "https://${DOMAIN},https://www.${DOMAIN}"
set_env_var "FRONTEND_URL" "https://${DOMAIN}"
set_env_var "EMAIL_HOST_USER" "$EMAIL_HOST_USER"
set_env_var "EMAIL_HOST_PASSWORD" "$EMAIL_HOST_PASSWORD"
set_env_var "DEFAULT_FROM_EMAIL" "$DEFAULT_FROM_EMAIL"
set_env_var "SERVER_EMAIL" "$SERVER_EMAIL"
set_env_var "TELEGRAM_WEBHOOK_SECRET" "$TELEGRAM_WEBHOOK_SECRET"

if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
  set_env_var "TELEGRAM_BOT_TOKEN" "$TELEGRAM_BOT_TOKEN"
  set_env_var "TELEGRAM_BOT_USERNAME" "$TELEGRAM_BOT_USERNAME"
else
  set_env_var "TELEGRAM_BOT_TOKEN" ""
fi

echo "[2/6] Preparing SSL certificates..."
mkdir -p "$SSL_DIR"

if [[ "$SELF_SIGNED_SSL" -eq 1 ]]; then
  openssl req -x509 -nodes -newkey rsa:2048 -days 30 \
    -keyout "${SSL_DIR}/key.pem" \
    -out "${SSL_DIR}/cert.pem" \
    -subj "/CN=${DOMAIN}"
else
  require_cmd docker
  run_root apt-get update
  run_root apt-get install -y certbot

  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
  else
    fail "Docker Compose is required"
  fi

  "${COMPOSE_CMD[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" stop nginx >/dev/null 2>&1 || true

  run_root certbot certonly --standalone \
    -d "$DOMAIN" -d "www.${DOMAIN}" \
    --agree-tos --no-eff-email --non-interactive \
    -m "$CERTBOT_EMAIL"

  run_root cp "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" "${SSL_DIR}/cert.pem"
  run_root cp "/etc/letsencrypt/live/${DOMAIN}/privkey.pem" "${SSL_DIR}/key.pem"
  run_root chmod 600 "${SSL_DIR}/key.pem"
fi

echo "[3/6] Running preflight checks..."
bash "${ROOT_DIR}/scripts/prod-preflight.sh"

echo "[4/6] Running deployment..."
bash "${ROOT_DIR}/deploy.sh"

echo "[5/6] Deployment status..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

echo "[6/6] Done."
echo "Site: https://${DOMAIN}"
echo "API docs: https://${DOMAIN}/api/docs/"

echo "If Telegram is enabled, verify with:"
echo "docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend python manage.py telegram_check"
