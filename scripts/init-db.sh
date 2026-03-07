#!/usr/bin/env bash
set -Eeuo pipefail

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${HOSPITOLL_ADMIN_PASSWORD:?HOSPITOLL_ADMIN_PASSWORD is required}"
: "${HOSPITOLL_APP_PASSWORD:?HOSPITOLL_APP_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v HOSPITOLL_ADMIN_PASSWORD="$HOSPITOLL_ADMIN_PASSWORD" \
  -v HOSPITOLL_APP_PASSWORD="$HOSPITOLL_APP_PASSWORD" \
  -f /opt/hospitoll/init.sql
