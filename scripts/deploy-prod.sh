#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

env_val() {
    grep -E "^$1=" .env | head -1 | cut -d= -f2-
}

BASE_DOMAIN=$(env_val BASE_DOMAIN)
PROM_BASIC_AUTH_USER=$(env_val PROM_BASIC_AUTH_USER)
PROM_BASIC_AUTH_HASH=$(env_val PROM_BASIC_AUTH_HASH)

sed \
    -e "s/__BASE_DOMAIN__/${BASE_DOMAIN}/g" \
    -e "s/__PROM_AUTH_USER__/${PROM_BASIC_AUTH_USER}/g" \
    -e "s|__PROM_AUTH_HASH__|${PROM_BASIC_AUTH_HASH}|g" \
    infra/caddy/Caddyfile.template > infra/caddy/Caddyfile

docker compose -f docker-compose.prod.yml up -d --build
