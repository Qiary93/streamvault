#!/usr/bin/env bash
# backup-mongo.sh — dump the MongoDB volume to ./backups/<timestamp>/
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; . "$DEPLOY_DIR/.env"; set +a

TS=$(date +%Y%m%d-%H%M%S)
DEST="$DEPLOY_DIR/backups/$TS"
mkdir -p "$DEST"

if [[ -n "${MONGO_ROOT_PASSWORD:-}" ]]; then
    docker exec sv-mongo mongodump \
        --username "${MONGO_ROOT_USER:-svadmin}" \
        --password "$MONGO_ROOT_PASSWORD" \
        --authenticationDatabase admin \
        --db "${DB_NAME:-streamvault}" \
        --archive > "$DEST/${DB_NAME:-streamvault}.archive"
else
    docker exec sv-mongo mongodump --db "${DB_NAME:-streamvault}" --archive \
        > "$DEST/${DB_NAME:-streamvault}.archive"
fi

echo "Backup written to $DEST"
