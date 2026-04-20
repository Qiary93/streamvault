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

log()  { printf '\033[1;36m[install]\033[0m %s\n' "$*"; }
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
    3. Paste your LiveKit / Stripe / S3 keys in $ENV_FILE, then
       'sudo systemctl restart streamvault' to pick them up.
=============================================================================
EOF
