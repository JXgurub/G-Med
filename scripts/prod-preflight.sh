#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.production"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.prod.yml"
SSL_DIR="${ROOT_DIR}/ssl"

required_values=(
    DJANGO_SECRET_KEY
    DB_PASSWORD
    HOSPITOLL_ADMIN_PASSWORD
    HOSPITOLL_APP_PASSWORD
    DOMAIN
    ALLOWED_HOSTS
    CORS_ALLOWED_ORIGINS
    CSRF_TRUSTED_ORIGINS
    FRONTEND_URL
)

if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: Missing .env.production at ${ENV_FILE}" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source <(tr -d '\r' < "$ENV_FILE")
set +a

missing=()
for key in "${required_values[@]}"; do
    value="${!key:-}"
    if [[ -z "$value" ]]; then
        missing+=("$key")
        continue
    fi
    case "$value" in
        change-this-*|"TODO"|"REPLACE_ME"|"example"|"example-*" )
            missing+=("$key")
            ;;
    esac
done

if (( ${#missing[@]} > 0 )); then
    echo "ERROR: The following production values are missing or still placeholders:" >&2
    printf '  - %s\n' "${missing[@]}" >&2
    exit 1
fi

for optional_key in TELEGRAM_BOT_TOKEN TELEGRAM_WEBHOOK_SECRET EMAIL_HOST_PASSWORD; do
    optional_value="${!optional_key:-}"
    case "$optional_value" in
        ""|change-this-*|"TODO"|"REPLACE_ME"|"example"|"example-*")
            echo "WARN: ${optional_key} is empty or still a placeholder; related features will be skipped or may not send mail." >&2
            ;;
    esac
done

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "ERROR: Missing compose file: ${COMPOSE_FILE}" >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    if ! command -v docker-compose >/dev/null 2>&1; then
        echo "ERROR: Docker Compose is required (docker compose or docker-compose)." >&2
        exit 1
    fi
fi

if [[ ! -f "${SSL_DIR}/cert.pem" || ! -f "${SSL_DIR}/key.pem" ]]; then
    echo "ERROR: SSL certificate files are missing in ${SSL_DIR}." >&2
    echo "Expected: cert.pem and key.pem" >&2
    exit 1
fi

echo "Preflight checks passed."