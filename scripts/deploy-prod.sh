#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
source .env
set +a

sed \
    -e "s/__BASE_DOMAIN__/${BASE_DOMAIN}/g" \
    -e "s/__PROM_AUTH_USER__/${PROM_BASIC_AUTH_USER}/g" \
    -e "s|__PROM_AUTH_HASH__|${PROM_BASIC_AUTH_HASH}|g" \
    infra/caddy/Caddyfile.template > infra/caddy/Caddyfile

docker compose -f docker-compose.prod.yml up -d --build
