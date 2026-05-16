#!/usr/bin/env bash
# =============================================================================
# StreamVault — one-shot installer for Ubuntu 24.04 LTS
# -----------------------------------------------------------------------------
# Installs Docker + Compose plugin, issues a Let's Encrypt certificate via the
# http-01 challenge, renders the nginx config, and brings the stack up.
#
# Usage (run from the project root):
#   sudo bash deploy/scripts/install.sh
#
# Re-running is safe — every step is idempotent.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"

C_YEL='\033[1;33m'; C_RESET='\033[0m'
log()  { printf '\033[1;36m[install]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n'      "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n'   "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n'  "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "This script must be run as root (use sudo)."

# -----------------------------------------------------------------------------
# 1. Ubuntu 24.04 check + base packages
# -----------------------------------------------------------------------------
log "Checking Ubuntu version…"
. /etc/os-release
[[ "$ID" == "ubuntu" ]] || warn "This script targets Ubuntu. Detected: $ID $VERSION_ID"

log "Updating apt cache…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release ufw openssl >/dev/null

# -----------------------------------------------------------------------------
# 2. Install Docker Engine + Compose plugin (official repo)
# -----------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker Engine…"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
    systemctl enable --now docker
else
    log "Docker is already installed — skipping."
fi

# -----------------------------------------------------------------------------
# 2b. Docker registry connectivity check.
# -----------------------------------------------------------------------------
# Many VPS providers (Contabo, OVH, sometimes Hetzner) advertise IPv6 but the
# route to Cloudflare's R2 CDN — which Docker Hub uses for blob storage — is
# broken or extremely slow. The result is that `docker pull mongo:7` (or any
# other image) hangs and fails with "i/o timeout" on an IPv6 address.
#
# We probe IPv6 reachability to the Docker registry. If it doesn't work AND
# the host has no /etc/docker/daemon.json yet, we write a safe IPv4-only
# defaults file so the image pull succeeds.
configure_docker_daemon() {
    local daemon_file=/etc/docker/daemon.json
    
    # If the operator already configured "ipv6", respect their choice.
    if [[ -f "$daemon_file" ]] && grep -q '"ipv6"' "$daemon_file" 2>/dev/null; then
        log "Existing /etc/docker/daemon.json — leaving as-is."
        return
    fi
    
    log "Probing Docker registry + R2 storage over IPv6…"
    # Two different hosts:
    #   • registry-1.docker.io       — Docker Hub registry API
    #   • r2.cloudflarestorage.com   — actual image-blob storage (where pulls
    #                                  hang on broken-IPv6 VPSes like yours)
    # Both must work for `docker pull` to succeed. We treat HTTP 200/401/403
    # as "reachable" — anything else (timeout, RST, NXDOMAIN) is broken.
    local probe_ok=true
    local code=""
    for host in registry-1.docker.io r2.cloudflarestorage.com; do
        code=$(timeout 6 curl -6 -sS --max-time 5 -o /dev/null -w "%{http_code}" "https://$host/" 2>/dev/null || echo "000")
        if [[ "$code" != "200" && "$code" != "401" && "$code" != "403" && "$code" != "400" ]]; then
            warn "IPv6 probe to $host returned '$code' — IPv6 routing is broken."
            probe_ok=false
            break
        fi
    done
    
    if $probe_ok; then
        log "IPv6 to Docker registry + R2 storage works — keeping defaults."
        return
    fi
    
    warn "Writing IPv4-only Docker daemon defaults to avoid pull timeouts."
    mkdir -p /etc/docker
    cat > "$daemon_file" <<'JSON'
{
  "ipv6": false,
  "dns": ["1.1.1.1", "8.8.8.8"]
}
JSON
    systemctl restart docker
    for i in 1 2 3 4 5 6 7 8 9 10; do
        if docker info >/dev/null 2>&1; then break; fi
        sleep 1
    done
    log "Docker daemon restarted with IPv4-only registry config."
}
configure_docker_daemon

# -----------------------------------------------------------------------------
# 3. Load config from .env
# -----------------------------------------------------------------------------
[[ -f "$ENV_FILE" ]] || die "Missing $ENV_FILE — copy deploy/.env.example to deploy/.env and fill in DOMAIN + LETSENCRYPT_EMAIL + JWT_SECRET."

set -a; . "$ENV_FILE"; set +a

: "${DOMAIN:?DOMAIN must be set in $ENV_FILE}"
: "${LETSENCRYPT_EMAIL:?LETSENCRYPT_EMAIL must be set in $ENV_FILE}"
: "${JWT_SECRET:?JWT_SECRET must be set in $ENV_FILE}"
: "${ADMIN_EMAIL:?ADMIN_EMAIL must be set in $ENV_FILE}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD must be set in $ENV_FILE}"

if [[ "$JWT_SECRET" == CHANGE_ME* ]]; then
    die "JWT_SECRET is still the placeholder. Generate one with: openssl rand -hex 48"
fi
if [[ "$ADMIN_PASSWORD" == CHANGE_ME* ]]; then
    die "ADMIN_PASSWORD is still the placeholder. Set a real strong password in $ENV_FILE."
fi

# -----------------------------------------------------------------------------
# 3b. MongoDB credentials — auto-generate if missing (upgrade path for installs
#     created before the auth-enabled compose file).
# -----------------------------------------------------------------------------
if [[ -z "${MONGO_ROOT_USER:-}" ]]; then
    MONGO_ROOT_USER="svadmin"
    echo "MONGO_ROOT_USER=$MONGO_ROOT_USER" >> "$ENV_FILE"
    log "Added MONGO_ROOT_USER=$MONGO_ROOT_USER to $ENV_FILE"
fi
if [[ -z "${MONGO_ROOT_PASSWORD:-}" || "$MONGO_ROOT_PASSWORD" == CHANGE_ME* ]]; then
    MONGO_ROOT_PASSWORD="$(openssl rand -hex 32)"
    sed -i '/^MONGO_ROOT_PASSWORD=/d' "$ENV_FILE"
    echo "MONGO_ROOT_PASSWORD=$MONGO_ROOT_PASSWORD" >> "$ENV_FILE"
    log "Generated a new MONGO_ROOT_PASSWORD (written to $ENV_FILE)."
fi

# -----------------------------------------------------------------------------
# 3b2. Interactive prompts — Stripe keys + StreamVault License code.
# -----------------------------------------------------------------------------
# Only prompts for values that are still empty in .env, so re-running this
# installer never overwrites keys you've already set. To re-edit existing
# values, use:  sudo bash deploy/scripts/set-keys.sh
prompt_env_value() {
    # prompt_env_value VAR_NAME "Friendly label" "Help / where to get it"
    local var="$1" label="$2" help="${3:-}"
    local current="${!var:-}"

    # Skip if already set (and not the placeholder).
    if [[ -n "$current" && "$current" != CHANGE_ME* ]]; then
        return
    fi

    printf '\n\033[1m%s\033[0m\n' "$label"
    [[ -n "$help" ]] && printf '\033[2m%s\033[0m\n' "$help"
    printf '  > '
    local value=""
    if [[ -t 0 ]]; then
        read -r value
    else
        read -r value </dev/tty 2>/dev/null || value=""
    fi
    value="${value#"${value%%[![:space:]]*}"}"        # ltrim
    value="${value%"${value##*[![:space:]]}"}"        # rtrim

    if [[ -z "$value" ]]; then
        printf '\033[1;33m  (skipped — you can set this later with: sudo bash %s/deploy/scripts/set-keys.sh)\033[0m\n' "$PROJECT_ROOT"
        return
    fi

    # Replace or append the line. Use a delimiter that won't appear in keys.
    if grep -q "^${var}=" "$ENV_FILE"; then
        # Escape the value for sed (handle |, &, /)
        local esc_value
        esc_value=$(printf '%s' "$value" | sed 's:[\\/&|]:\\&:g')
        sed -i "s|^${var}=.*|${var}=${esc_value}|" "$ENV_FILE"
    else
        echo "${var}=${value}" >> "$ENV_FILE"
    fi
    export "$var=$value"
    printf '\033[1;32m  ✓ saved to %s\033[0m\n' "$ENV_FILE"
}

echo
printf '\033[1;36m═══════════════════════════════════════════════════════════════\033[0m\n'
printf '\033[1;36m  Optional API keys\033[0m\n'
printf '\033[1;36m═══════════════════════════════════════════════════════════════\033[0m\n'
printf '\033[2mLeave any field blank to skip. You can set/update them later by running:\033[0m\n'
printf '\033[2m  sudo bash %s/deploy/scripts/set-keys.sh\033[0m\n' "$PROJECT_ROOT"

prompt_env_value STRIPE_API_KEY \
    "Stripe secret API key" \
    "Get it from https://dashboard.stripe.com/apikeys (use a restricted key in prod). Starts with sk_live_… or sk_test_…"

prompt_env_value STRIPE_CONNECT_WEBHOOK_SECRET \
    "Stripe Connect webhook signing secret" \
    "Stripe → Developers → Webhooks → endpoint /api/webhook/stripe/connect → 'Signing secret'. Starts with whsec_…"

prompt_env_value STREAMVAULT_LICENSE_KEY \
    "StreamVault License code" \
    "Buy or retrieve from https://license.stream-vault.eu/dashboard. Format: SVL-XXXXX-XXXXX-XXXXX-XXXXX (any prefix works)."

# -----------------------------------------------------------------------------
# 3c. Detect MongoDB auth-mismatch from older installs.
# -----------------------------------------------------------------------------
# Background: MongoDB only reads MONGO_INITDB_ROOT_USERNAME/PASSWORD when the
# data volume is initialized for the FIRST time. If a user upgraded from an
# older docker-compose.yml that didn't enable auth, their existing volume has
# no auth set up — but the new docker-compose tells the backend to authenticate,
# so the backend can never connect.
#
# We detect this BEFORE building/starting the new stack and recover automatically.
mongo_auth_health_check() {
    # Returns 0 if mongo is reachable AND auth works (or auth is not yet
    # configured), 1 if there's a mismatch we should recover from.
    local container=sv-mongo
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        return 0  # not running yet — nothing to check
    fi
    
    # Try with creds (new auth-enabled install)
    if docker exec "$container" mongosh --quiet \
            -u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" \
            --authenticationDatabase admin \
            --eval "db.adminCommand('ping').ok" 2>/dev/null | grep -q "^1$"; then
        return 0
    fi
    
    # Try without creds (old no-auth install)
    if docker exec "$container" mongosh --quiet \
            --eval "db.adminCommand('ping').ok" 2>/dev/null | grep -q "^1$"; then
        # Reachable WITHOUT auth → volume is no-auth → mismatch with new compose
        return 1
    fi
    
    # Mongo is up but neither path worked — could be transient
    return 2
}

if docker volume inspect streamvault_mongo-data >/dev/null 2>&1; then
    # Volume exists from a prior install. Spin mongo up in isolation to test it.
    log "Detected existing MongoDB volume — verifying auth compatibility…"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d mongo >/dev/null 2>&1 || true
    sleep 5
    
    set +e
    mongo_auth_health_check
    auth_status=$?
    set -e
    
    if [[ $auth_status -eq 1 ]]; then
        warn "Existing MongoDB volume has NO authentication, but the current"
        warn "deployment requires it. The backend cannot connect to this volume."
        warn ""
        warn "Recovery requires re-initializing the volume. Your data will be"
        warn "backed up first — find it at $DEPLOY_DIR/backups/<timestamp>/"
        warn ""
        printf "${C_YEL}?${C_RESET} Auto-recover (backup → wipe → reinit with auth)? [Y/n] "
        # Read from /dev/tty so this works inside curl-piped bootstrap too.
        ans="y"
        if [[ -t 0 ]] || [[ -e /dev/tty ]]; then
            read -r ans </dev/tty || ans="y"
        fi
        ans="${ans:-y}"
        if [[ "$ans" != [yY]* ]]; then
            die "Aborted by operator. To recover manually: backup-mongo.sh, then 'docker compose down && docker volume rm streamvault_mongo-data streamvault_mongo-config'."
        fi
        
        log "Backing up existing MongoDB volume…"
        bash "$DEPLOY_DIR/scripts/backup-mongo.sh" || warn "Backup failed — continuing anyway."
        
        log "Stopping stack and removing un-authenticated volume…"
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down >/dev/null 2>&1 || true
        docker volume rm streamvault_mongo-data streamvault_mongo-config >/dev/null 2>&1 || true
        ok "Old volume removed — fresh init with auth will happen on next 'up'."
    elif [[ $auth_status -eq 2 ]]; then
        warn "MongoDB is up but neither authenticated nor anonymous ping worked."
        warn "Will continue; if the backend fails to start, re-run install.sh to retry."
    else
        log "MongoDB auth check passed."
    fi
fi

log "Domain:       $DOMAIN"
log "Admin email:  $ADMIN_EMAIL"

# -----------------------------------------------------------------------------
# 4. Firewall — open 22, 80, 443
# -----------------------------------------------------------------------------
log "Configuring UFW firewall (allow 22/80/443)…"
ufw allow 22/tcp    >/dev/null || true
ufw allow 80/tcp    >/dev/null || true
ufw allow 443/tcp   >/dev/null || true
yes | ufw enable    >/dev/null || true

# -----------------------------------------------------------------------------
# 5. DNS sanity check — warn if A record doesn't resolve to this host.
# -----------------------------------------------------------------------------
SERVER_IP=$(curl -fsSL https://api.ipify.org 2>/dev/null || echo "unknown")
DOMAIN_IP=$(getent ahostsv4 "$DOMAIN" | awk '{print $1; exit}' || true)
if [[ "$SERVER_IP" != "unknown" && "$DOMAIN_IP" != "$SERVER_IP" ]]; then
    warn "DNS for $DOMAIN resolves to '$DOMAIN_IP' but this server's public IP is '$SERVER_IP'."
    warn "Let's Encrypt issuance will FAIL until the A record points here. Fix DNS and re-run."
    read -r -p "Continue anyway? [y/N] " yn
    [[ "$yn" == [yY]* ]] || die "Aborted by operator."
fi

# -----------------------------------------------------------------------------
# 6. Let's Encrypt — issue cert on first run using a throwaway nginx.
# -----------------------------------------------------------------------------
CERT_PATH="/var/lib/docker/volumes/streamvault_letsencrypt/_data/live/$DOMAIN/fullchain.pem"

if [[ ! -f "$CERT_PATH" ]]; then
    log "Issuing Let's Encrypt certificate for $DOMAIN…"
    docker volume create streamvault_letsencrypt      >/dev/null
    docker volume create streamvault_certbot-webroot  >/dev/null

    # Start a temporary nginx that serves ONLY the ACME challenge on :80.
    docker rm -f sv-certbot-bootstrap >/dev/null 2>&1 || true
    docker run -d --name sv-certbot-bootstrap --rm \
        -p 80:80 \
        -v streamvault_certbot-webroot:/var/www/certbot \
        nginx:1.27-alpine \
        sh -c 'printf "server { listen 80; location /.well-known/acme-challenge/ { root /var/www/certbot; } location / { return 200 ok; } }" > /etc/nginx/conf.d/default.conf && nginx -g "daemon off;"' \
        >/dev/null

    sleep 2

    docker run --rm \
        -v streamvault_letsencrypt:/etc/letsencrypt \
        -v streamvault_certbot-webroot:/var/www/certbot \
        certbot/certbot:latest certonly \
            --webroot -w /var/www/certbot \
            --email "$LETSENCRYPT_EMAIL" \
            --agree-tos --no-eff-email --non-interactive \
            -d "$DOMAIN"

    docker rm -f sv-certbot-bootstrap >/dev/null 2>&1 || true
    log "Certificate issued ✓"
else
    log "Certificate already exists — skipping issuance (auto-renewal handled by the certbot container)."
fi

# -----------------------------------------------------------------------------
# 7. Build & start the stack
# -----------------------------------------------------------------------------
log "Building Docker images (this can take 3–8 minutes the first time)…"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build

log "Starting services…"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

# -----------------------------------------------------------------------------
# 7b. Post-startup health check.
# -----------------------------------------------------------------------------
# Verify the backend container is actually running (not crash-looping). This
# catches:
#   • aiosmtplib / missing-python-dep issues
#   • MongoDB auth mismatches that snuck past the earlier check
#   • Any other container that died on startup
log "Waiting up to 90s for backend to become healthy…"
backend_ready=false
for i in $(seq 1 18); do
    sleep 5
    state=$(docker inspect -f '{{.State.Status}}' sv-backend 2>/dev/null || echo "missing")
    restarts=$(docker inspect -f '{{.RestartCount}}' sv-backend 2>/dev/null || echo "0")
    if [[ "$state" == "running" && "$restarts" -lt 3 ]]; then
        # Also probe the API to confirm it's actually serving requests
        if docker exec sv-backend curl -fsS --max-time 3 http://127.0.0.1:8001/api/config/features >/dev/null 2>&1; then
            backend_ready=true
            break
        fi
    fi
done

if ! $backend_ready; then
    state=$(docker inspect -f '{{.State.Status}}' sv-backend 2>/dev/null || echo "missing")
    restarts=$(docker inspect -f '{{.RestartCount}}' sv-backend 2>/dev/null || echo "0")
    warn "Backend container did not become healthy. Status='$state' restarts=$restarts"
    warn "Last 40 log lines from sv-backend:"
    echo "----------------------------------------------------------------------"
    docker logs sv-backend --tail 40 2>&1 || true
    echo "----------------------------------------------------------------------"
    warn "Common causes & fixes:"
    warn "  • ModuleNotFoundError → 'cd $PROJECT_ROOT && git pull' for fixes,"
    warn "    then 'docker compose -f $COMPOSE_FILE build --no-cache backend &&"
    warn "    docker compose -f $COMPOSE_FILE up -d backend'"
    warn "  • MongoServerSelectionError / Authentication failed → re-run install.sh"
    warn "    (it auto-detects auth mismatches and offers to recover the volume)"
    die "Aborting before installing systemd unit. Fix backend, then re-run."
fi
ok "Backend is healthy and responding on /api."

# -----------------------------------------------------------------------------
# 8. Install systemd unit so the stack survives reboots
# -----------------------------------------------------------------------------
SYSTEMD_UNIT=/etc/systemd/system/streamvault.service
log "Installing systemd unit at $SYSTEMD_UNIT…"
cat > "$SYSTEMD_UNIT" <<EOF
[Unit]
Description=StreamVault — Docker Compose stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DEPLOY_DIR
EnvironmentFile=$ENV_FILE
ExecStart=/usr/bin/docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d
ExecStop=/usr/bin/docker compose -f $COMPOSE_FILE --env-file $ENV_FILE down
ExecReload=/usr/bin/docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d --build
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable streamvault.service

# -----------------------------------------------------------------------------
# 8b. Install the auto-updater (path watcher + oneshot service).
# -----------------------------------------------------------------------------
# Backend container drops a marker file at $PROJECT_ROOT/.update-state/requested
# when an admin clicks "Update" in the panel. systemd's path-watcher picks it
# up and runs deploy/scripts/updater.sh as root on the host (where it has the
# privileges to git-pull, build, and recreate containers).
log "Installing auto-updater systemd units…"

UPDATE_STATE_DIR="$PROJECT_ROOT/.update-state"
mkdir -p "$UPDATE_STATE_DIR"
# Make the dir writable by anyone (the backend container runs as root inside
# its namespace, so it can already write here, but explicit perms protect us
# if the user later decides to run the backend as a non-root UID).
chmod 0777 "$UPDATE_STATE_DIR"

UPDATER_SERVICE=/etc/systemd/system/streamvault-updater.service
cat > "$UPDATER_SERVICE" <<EOF
[Unit]
Description=StreamVault — apply update from GitHub
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=$PROJECT_ROOT
Environment=PROJECT_DIR=$PROJECT_ROOT
ExecStart=/usr/bin/env bash $DEPLOY_DIR/scripts/updater.sh
TimeoutStartSec=1800

[Install]
WantedBy=multi-user.target
EOF

UPDATER_PATH=/etc/systemd/system/streamvault-updater.path
cat > "$UPDATER_PATH" <<EOF
[Unit]
Description=Watch for StreamVault update requests
After=streamvault.service

[Path]
PathExists=$UPDATE_STATE_DIR/requested
Unit=streamvault-updater.service

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now streamvault-updater.path
ok "Auto-updater installed (path-watcher → oneshot service)."

# -----------------------------------------------------------------------------
# 9. Post-install summary
# -----------------------------------------------------------------------------
cat <<EOF

=============================================================================
  StreamVault is live — https://$DOMAIN
=============================================================================
  Admin login:   $ADMIN_EMAIL
  Admin panel:   https://$DOMAIN/admin

  Useful commands:
    View logs:        docker compose -f $COMPOSE_FILE logs -f
    Restart stack:    sudo systemctl restart streamvault
    Stop stack:       sudo systemctl stop streamvault
    Update & rebuild: cd $PROJECT_ROOT && git pull && \\
                      sudo systemctl reload streamvault

  Next steps:
    1. Log in at https://$DOMAIN/admin and change the admin password.
    2. Configure SMTP in Admin → Email settings.
    3. Update Stripe keys / License code anytime (no .env editing needed):
         sudo bash $DEPLOY_DIR/scripts/set-keys.sh           # interactive
         sudo bash $DEPLOY_DIR/scripts/set-keys.sh --show    # see current
    4. To change LiveKit / S3 keys, edit $ENV_FILE then
       'sudo systemctl restart streamvault' to pick them up.
=============================================================================
EOF
