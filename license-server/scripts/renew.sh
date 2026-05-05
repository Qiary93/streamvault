#!/usr/bin/env bash
# renew.sh — renews Let's Encrypt certificate (run via cron, once a month is fine).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
docker compose run --rm certbot renew --webroot -w /var/www/certbot
docker compose exec nginx nginx -s reload || docker compose restart nginx
