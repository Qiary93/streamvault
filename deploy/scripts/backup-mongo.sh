#!/usr/bin/env bash
# backup-mongo.sh — dump the MongoDB volume to ./backups/<timestamp>/
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$DEPLOY_DIR/.env"

TS=$(date +%Y%m%d-%H%M%S)
DEST="$DEPLOY_DIR/backups/$TS"
mkdir -p "$DEST"

docker exec sv-mongo mongodump --db "${DB_NAME:-streamvault}" --archive > "$DEST/${DB_NAME:-streamvault}.archive"
echo "Backup written to $DEST"
