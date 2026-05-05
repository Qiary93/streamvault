#!/usr/bin/env bash
# backup.sh — MongoDB backup for the license server.
# Creates a timestamped archive under backups/ inside the project dir.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
TS="$(date -u +%Y%m%d_%H%M%S)"
OUT_DIR="$PROJECT_DIR/backups/$TS"
mkdir -p "$OUT_DIR"
docker compose exec -T mongo mongodump --archive --gzip --db "${DB_NAME:-stream_vault_license}" > "$OUT_DIR/dump.archive.gz"
echo "Backup written to $OUT_DIR/dump.archive.gz"
# Keep the 30 most-recent backups
ls -1dt "$PROJECT_DIR"/backups/*/ 2>/dev/null | tail -n +31 | xargs -r rm -rf
