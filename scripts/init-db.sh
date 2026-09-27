#!/usr/bin/env bash
set -Eeuo pipefail

# This script is mounted into Docker's initdb directory and must be a regular file,
# not a directory. It must connect as the PostgreSQL user created by the container,
# otherwise the init step fails with "role postgres does not exist".

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${HOSPITOLL_ADMIN_PASSWORD:?HOSPITOLL_ADMIN_PASSWORD is required}"
: "${HOSPITOLL_APP_PASSWORD:?HOSPITOLL_APP_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 \
     -U "${POSTGRES_USER}" \
     -d "${POSTGRES_DB}" \
     -v "HOSPITOLL_ADMIN_PASSWORD=${HOSPITOLL_ADMIN_PASSWORD}" \
     -v "HOSPITOLL_APP_PASSWORD=${HOSPITOLL_APP_PASSWORD}" \
     -f /opt/hospitoll/init.sql
