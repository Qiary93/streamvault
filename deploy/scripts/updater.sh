#!/usr/bin/env bash
# updater.sh — runs on the HOST (not in a container) when the backend writes
# /opt/streamvault/.update-state/requested. Triggered by streamvault-updater.path.
#
# Writes status to /opt/streamvault/.update-state/status.json so the admin UI
# can poll it.
set -uo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/streamvault}"
STATE_DIR="$PROJECT_DIR/.update-state"
STATUS_FILE="$STATE_DIR/status.json"
LOG_FILE="$STATE_DIR/log.txt"
COMPOSE_FILE="$PROJECT_DIR/deploy/docker-compose.yml"
ENV_FILE="$PROJECT_DIR/deploy/.env"

mkdir -p "$STATE_DIR"

# Acquire a lock so concurrent triggers don't stomp on each other.
exec 9>"$STATE_DIR/.lock"
if ! flock -n 9; then
    echo "Another update is already running — exiting." >&2
    exit 1
fi

# Consume the trigger first so a re-fire while we run is queued, not racy.
rm -f "$STATE_DIR/requested" 2>/dev/null || true

now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

write_status() {
    local status="$1" stage="$2" message="$3" started_at="$4" finished_at="${5:-}"
    cat > "$STATUS_FILE" <<EOF
{
  "status": "$status",
  "stage": "$stage",
  "message": $(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$message"),
  "started_at": "$started_at",
  "finished_at": $( [ -n "$finished_at" ] && python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$finished_at" || echo null )
}
EOF
}

start_ts="$(now)"
: > "$LOG_FILE"

run_step() {
    local stage="$1"; shift
    write_status "running" "$stage" "Running: $*" "$start_ts"
    {
        echo "===== [$stage] $* ====="
        "$@" 2>&1
        echo "===== exit=$? ====="
    } >>"$LOG_FILE" 2>&1
}

write_status "running" "git_pull" "Fetching latest changes…" "$start_ts"

cd "$PROJECT_DIR" || { write_status "error" "init" "PROJECT_DIR not found: $PROJECT_DIR" "$start_ts" "$(now)"; exit 1; }

if ! run_step "git_pull" git fetch --all --prune; then
    write_status "error" "git_pull" "git fetch failed — see log_tail" "$start_ts" "$(now)"
    exit 1
fi
if ! run_step "git_pull" git reset --hard "@{upstream}"; then
    write_status "error" "git_pull" "git reset --hard failed — see log_tail" "$start_ts" "$(now)"
    exit 1
fi

write_status "running" "build" "Building Docker images (this can take 3–10 min)…" "$start_ts"
if ! run_step "build" docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build; then
    write_status "error" "build" "docker compose build failed — see log_tail" "$start_ts" "$(now)"
    exit 1
fi

write_status "running" "up" "Recreating containers…" "$start_ts"
if ! run_step "up" docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d; then
    write_status "error" "up" "docker compose up failed — see log_tail" "$start_ts" "$(now)"
    exit 1
fi

# Smoke-test the new backend
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
    write_status "success" "done" "Update completed successfully." "$start_ts" "$(now)"
else
    write_status "error" "health" "Backend did not become healthy after rebuild — check 'docker logs sv-backend'." "$start_ts" "$(now)"
    exit 1
fi
