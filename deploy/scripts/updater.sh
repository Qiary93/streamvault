#!/usr/bin/env bash
# updater.sh — runs on the HOST when the backend writes
# /opt/streamvault/.update-state/requested. Triggered by streamvault-updater.path.
#
# Modes (read from .update-state/request.json):
#   mode=update     git fetch + reset --hard @{upstream}
#   mode=rollback   git checkout <target_sha>
#
# Pre-flight: writes pre-update DB backup via deploy/scripts/backup-mongo.sh.
# Outcome:    appends an entry to .update-state/history.json (audit log).
set -uo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/streamvault}"
STATE_DIR="$PROJECT_DIR/.update-state"
STATUS_FILE="$STATE_DIR/status.json"
LOG_FILE="$STATE_DIR/log.txt"
HISTORY_FILE="$STATE_DIR/history.json"
REQUEST_FILE="$STATE_DIR/requested"
REQUEST_PARAMS="$STATE_DIR/request.json"
COMPOSE_FILE="$PROJECT_DIR/deploy/docker-compose.yml"
ENV_FILE="$PROJECT_DIR/deploy/.env"
BACKUP_SCRIPT="$PROJECT_DIR/deploy/scripts/backup-mongo.sh"

mkdir -p "$STATE_DIR"
exec 9>"$STATE_DIR/.lock"
if ! flock -n 9; then
    echo "Another update is already running — exiting." >&2
    exit 1
fi

# Consume the trigger
rm -f "$REQUEST_FILE" 2>/dev/null || true

now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# Read request params (mode + optional target_sha)
MODE="update"
TARGET_SHA=""
if [[ -f "$REQUEST_PARAMS" ]]; then
    MODE=$(python3 -c "import json,sys; print(json.load(open('$REQUEST_PARAMS')).get('mode','update'))" 2>/dev/null || echo "update")
    TARGET_SHA=$(python3 -c "import json,sys; print(json.load(open('$REQUEST_PARAMS')).get('target_sha',''))" 2>/dev/null || echo "")
fi

py_json_str() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

write_status() {
    local status="$1" stage="$2" message="$3" started_at="$4" finished_at="${5:-}"
    cat > "$STATUS_FILE" <<EOF
{
  "status": "$status",
  "stage": "$stage",
  "mode": "$MODE",
  "message": $(py_json_str "$message"),
  "started_at": "$started_at",
  "finished_at": $( [ -n "$finished_at" ] && py_json_str "$finished_at" || echo null )
}
EOF
}

append_history() {
    local from_sha="$1" to_sha="$2" status="$3" message="$4"
    python3 - <<PY
import json, os
hf = "$HISTORY_FILE"
items = []
if os.path.exists(hf):
    try: items = json.load(open(hf))
    except: items = []
if not isinstance(items, list): items = []
items.append({
    "started_at": "$start_ts",
    "finished_at": "$(now)",
    "mode": "$MODE",
    "from_sha": "$from_sha",
    "to_sha": "$to_sha",
    "status": "$status",
    "message": $(py_json_str "$message"),
})
items = items[-100:]
json.dump(items, open(hf, "w"), indent=2)
PY
}

run_step() {
    local stage="$1"; shift
    {
        echo "===== [$stage] $* ====="
        "$@" 2>&1
        echo "===== exit=$? ====="
    } >>"$LOG_FILE" 2>&1
}

start_ts="$(now)"
: > "$LOG_FILE"
cd "$PROJECT_DIR" || { write_status "error" "init" "PROJECT_DIR not found" "$start_ts" "$(now)"; exit 1; }

CURRENT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")

# -------- pre-update DB backup (best-effort) --------
write_status "running" "backup" "Backing up MongoDB before update…" "$start_ts"
if [[ -x "$BACKUP_SCRIPT" ]] || [[ -f "$BACKUP_SCRIPT" ]]; then
    if ! run_step "backup" bash "$BACKUP_SCRIPT"; then
        # Don't abort the update on backup failure — just record it.
        echo "WARNING: backup-mongo.sh failed; continuing update anyway." >>"$LOG_FILE"
    fi
fi

# -------- git phase --------
if [[ "$MODE" == "rollback" ]]; then
    if [[ -z "$TARGET_SHA" ]]; then
        write_status "error" "rollback" "No target_sha provided for rollback" "$start_ts" "$(now)"
        append_history "$CURRENT_SHA" "" "error" "Rollback aborted — no target SHA"
        exit 1
    fi
    write_status "running" "rollback" "Rolling back to $TARGET_SHA…" "$start_ts"
    if ! run_step "rollback" git fetch --all --prune; then
        write_status "error" "rollback" "git fetch failed" "$start_ts" "$(now)"
        append_history "$CURRENT_SHA" "" "error" "git fetch failed"
        exit 1
    fi
    if ! run_step "rollback" git reset --hard "$TARGET_SHA"; then
        write_status "error" "rollback" "git reset --hard $TARGET_SHA failed" "$start_ts" "$(now)"
        append_history "$CURRENT_SHA" "$TARGET_SHA" "error" "git reset failed"
        exit 1
    fi
else
    write_status "running" "git_pull" "Fetching latest changes…" "$start_ts"
    if ! run_step "git_pull" git fetch --all --prune; then
        write_status "error" "git_pull" "git fetch failed — see log_tail" "$start_ts" "$(now)"
        append_history "$CURRENT_SHA" "" "error" "git fetch failed"
        exit 1
    fi
    if ! run_step "git_pull" git reset --hard "@{upstream}"; then
        write_status "error" "git_pull" "git reset --hard failed — see log_tail" "$start_ts" "$(now)"
        append_history "$CURRENT_SHA" "" "error" "git reset failed"
        exit 1
    fi
fi

NEW_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")

# -------- build + up --------
write_status "running" "build" "Building Docker images…" "$start_ts"
if ! run_step "build" docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build; then
    write_status "error" "build" "docker compose build failed — see log_tail" "$start_ts" "$(now)"
    append_history "$CURRENT_SHA" "$NEW_SHA" "error" "docker compose build failed"
    exit 1
fi

write_status "running" "up" "Recreating containers…" "$start_ts"
if ! run_step "up" docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d; then
    write_status "error" "up" "docker compose up failed — see log_tail" "$start_ts" "$(now)"
    append_history "$CURRENT_SHA" "$NEW_SHA" "error" "docker compose up failed"
    exit 1
fi

# -------- health check --------
sleep 8
write_status "running" "health" "Verifying backend health…" "$start_ts"
ok=false
for i in 1 2 3 4 5 6 7 8 9 10; do
    if docker exec sv-backend curl -fsS --max-time 3 http://127.0.0.1:8001/api/config/features >/dev/null 2>&1; then
        ok=true; break
    fi
    sleep 3
done

if $ok; then
    if [[ "$MODE" == "rollback" ]]; then
        write_status "success" "done" "Rollback to $TARGET_SHA completed successfully." "$start_ts" "$(now)"
        append_history "$CURRENT_SHA" "$NEW_SHA" "success" "Rollback completed"
    else
        write_status "success" "done" "Update completed successfully." "$start_ts" "$(now)"
        append_history "$CURRENT_SHA" "$NEW_SHA" "success" "Update completed"
    fi
else
    write_status "error" "health" "Backend did not become healthy after deploy — check 'docker logs sv-backend'." "$start_ts" "$(now)"
    append_history "$CURRENT_SHA" "$NEW_SHA" "error" "Backend health check failed"
    exit 1
fi
