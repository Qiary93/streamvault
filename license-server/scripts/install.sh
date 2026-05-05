#!/usr/bin/env bash
#
# install.sh — automated installer for the StreamVault License Server.
#
# Usage:
#   sudo bash install.sh [DOMAIN] [ADMIN_EMAIL]
#
# Examples:
#   sudo bash install.sh license.stream-vault.eu you@example.com
#   sudo bash install.sh                                     # prompts for both
#
# What it does:
#   1. Installs docker + docker compose + certbot if missing
#   2. Verifies DNS for the given subdomain resolves to this VPS
#   3. Generates secrets (JWT, MongoDB) and writes them to .env
#   4. Templates nginx.conf with the real domain
#   5. Requests a Let's Encrypt cert (HTTP-01) for the subdomain
#   6. Brings the stack up with `docker compose up -d`
#   7. Prints next steps (Stripe webhook, admin account, etc.)
#
# Idempotent: re-running updates the domain without nuking the DB.
# -----------------------------------------------------------------------------

set -euo pipefail

# ---------- styling ----------
BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'
YELLOW=$'\033[33m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
log()  { echo "${CYAN}▸${RESET} $*"; }
ok()   { echo "${GREEN}✓${RESET} $*"; }
warn() { echo "${YELLOW}!${RESET} $*"; }
die()  { echo "${RED}✗${RESET} $*" >&2; exit 1; }
step() { echo; echo "${BOLD}${CYAN}═══ $* ═══${RESET}"; }

[[ $EUID -eq 0 ]] || die "Please run as root (use sudo)."

# ---------- locate project dir ----------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
ENV_FILE="$PROJECT_DIR/.env"
NGINX_FILE="$PROJECT_DIR/nginx.conf"

[[ -f "$COMPOSE_FILE" ]] || die "docker-compose.yml not found at $COMPOSE_FILE — are you running this from scripts/ inside the license-server repo?"

# ---------- collect inputs ----------
DOMAIN="${1:-}"
ADMIN_EMAIL="${2:-}"

if [[ -z "$DOMAIN" ]]; then
    read -rp "Enter the domain for the license server (e.g. license.stream-vault.eu): " DOMAIN
fi
if [[ -z "$ADMIN_EMAIL" ]]; then
    read -rp "Enter the admin email (used for SSL + license-sale notifications): " ADMIN_EMAIL
fi

DOMAIN="${DOMAIN,,}"  # lowercase
[[ -n "$DOMAIN" ]]       || die "Domain is required"
[[ -n "$ADMIN_EMAIL" ]]  || die "Admin email is required"
[[ "$DOMAIN" =~ ^[a-z0-9.-]+\.[a-z]{2,}$ ]] || die "Domain '$DOMAIN' doesn't look valid"

log "Domain:      ${BOLD}$DOMAIN${RESET}"
log "Admin email: ${BOLD}$ADMIN_EMAIL${RESET}"

# ---------- 1. install system packages ----------
step "1/7  System packages"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -yq \
    ca-certificates curl gnupg dnsutils openssl ufw certbot >/dev/null
ok "base packages"

if ! command -v docker >/dev/null; then
    log "Installing Docker Engine…"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -yq \
        docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
    systemctl enable --now docker
fi
ok "docker $(docker --version | awk '{print $3}' | tr -d ',')"

# ---------- 2. verify DNS ----------
step "2/7  DNS check"

VPS_IP="$(curl -s -4 ifconfig.me || curl -s -4 api.ipify.org || true)"
[[ -n "$VPS_IP" ]] || die "Could not detect this VPS's public IP"
log "This VPS public IP: ${BOLD}$VPS_IP${RESET}"

DNS_IP="$(dig +short "$DOMAIN" A @1.1.1.1 | tail -n 1)"
if [[ -z "$DNS_IP" ]]; then
    warn "DNS lookup for ${BOLD}$DOMAIN${RESET} returned nothing."
    cat <<EOF

${YELLOW}You need to create a DNS A record before continuing:${RESET}

    ${BOLD}Type:${RESET}    A
    ${BOLD}Name:${RESET}    ${DOMAIN%%.*}          ${DIM}(the subdomain part)${RESET}
    ${BOLD}Value:${RESET}   $VPS_IP
    ${BOLD}TTL:${RESET}     300 (5 minutes)

Log in to your domain registrar / DNS provider (Cloudflare, Namecheap, GoDaddy,
OVH, Hetzner DNS, etc.) and add that record to the zone for the parent domain
(${DOMAIN#*.}).

DNS propagation usually takes 1–5 minutes. You can check with:
    dig +short $DOMAIN

Re-run this installer once the A record resolves to $VPS_IP.
EOF
    die "DNS not configured yet"
fi

if [[ "$DNS_IP" != "$VPS_IP" ]]; then
    warn "DNS for $DOMAIN resolves to ${BOLD}$DNS_IP${RESET}, but this VPS is ${BOLD}$VPS_IP${RESET}."
    echo "Fix the A record (see instructions above) and wait for propagation, then re-run."
    die "DNS mismatch"
fi
ok "$DOMAIN → $VPS_IP (matches this VPS)"

# ---------- 3. firewall ----------
step "3/7  Firewall"

if ufw status | grep -q "Status: active"; then
    ufw allow 22/tcp  >/dev/null || true
    ufw allow 80/tcp  >/dev/null || true
    ufw allow 443/tcp >/dev/null || true
    ok "UFW: ports 22, 80, 443 allowed"
else
    ufw allow 22/tcp  >/dev/null 2>&1 || true
    ufw allow 80/tcp  >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    warn "UFW not active — enabling it is recommended: ${BOLD}ufw enable${RESET}"
fi

# ---------- 4. .env ----------
step "4/7  Environment file"

if [[ ! -f "$ENV_FILE" ]]; then
    log "Generating $ENV_FILE with fresh secrets"
    JWT_SECRET="$(openssl rand -hex 64)"
    cat > "$ENV_FILE" <<EOF
# Auto-generated by install.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ).
# Edit freely — re-running install.sh preserves existing values.

MONGO_URL=mongodb://mongo:27017
DB_NAME=stream_vault_license

JWT_SECRET=$JWT_SECRET

# ⚠️ Paste your real Stripe keys here.
# Get them from https://dashboard.stripe.com/apikeys
# Use sk_test_* during setup, swap to sk_live_* when you're ready to sell.
STRIPE_SECRET_KEY=sk_test_REPLACE_ME
# The webhook secret comes from https://dashboard.stripe.com/webhooks
# after you add an endpoint pointing at https://$DOMAIN/api/webhook/stripe
STRIPE_WEBHOOK_SECRET=whsec_REPLACE_ME

FRONTEND_URL=https://$DOMAIN
ADMIN_NOTIFY_EMAIL=$ADMIN_EMAIL

# Optional: SMTP for license-issued emails (leave blank to disable)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=no-reply@${DOMAIN#*.}
EOF
    ok "wrote fresh .env (update STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET!)"
else
    # .env exists — update only the fields that depend on the domain.
    sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=https://$DOMAIN|" "$ENV_FILE"
    sed -i "s|^ADMIN_NOTIFY_EMAIL=.*|ADMIN_NOTIFY_EMAIL=$ADMIN_EMAIL|" "$ENV_FILE"
    if grep -q "^SMTP_FROM=$" "$ENV_FILE" || ! grep -q "^SMTP_FROM=" "$ENV_FILE"; then
        sed -i "s|^SMTP_FROM=.*|SMTP_FROM=no-reply@${DOMAIN#*.}|" "$ENV_FILE"
    fi
    ok "existing .env kept, domain-dependent fields updated"
fi

# ---------- 5. nginx.conf ----------
step "5/7  Nginx config"

cat > "$NGINX_FILE" <<EOF
# Auto-generated by install.sh for $DOMAIN on $(date -u +%Y-%m-%dT%H:%M:%SZ).
# Re-running install.sh rewrites this file; manual edits will be lost.

server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    client_max_body_size 5m;

    # Stripe webhooks need the raw request body — disable buffering on this path.
    location /api/webhook/stripe {
        proxy_pass http://backend:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_request_buffering off;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
ok "nginx.conf generated for $DOMAIN"

# ---------- 6. SSL certificate ----------
step "6/7  SSL certificate (Let's Encrypt)"

CERT_DIR="$PROJECT_DIR/certbot/conf"
WEBROOT="$PROJECT_DIR/certbot/www"
mkdir -p "$CERT_DIR" "$WEBROOT"

if [[ -f "$CERT_DIR/live/$DOMAIN/fullchain.pem" ]]; then
    ok "existing cert for $DOMAIN found — will auto-renew"
else
    log "Requesting cert for $DOMAIN via HTTP-01 challenge…"

    # Temporarily stop anything on port 80 (so certbot's standalone mode works)
    cd "$PROJECT_DIR"
    docker compose --env-file "$ENV_FILE" down 2>/dev/null || true
    systemctl stop nginx 2>/dev/null || true

    certbot certonly \
        --standalone \
        --non-interactive \
        --agree-tos \
        -m "$ADMIN_EMAIL" \
        -d "$DOMAIN" \
        --config-dir "$CERT_DIR" \
        --work-dir /tmp/certbot-work \
        --logs-dir /tmp/certbot-log
    ok "cert issued for $DOMAIN"
fi

# ---------- 7. boot the stack ----------
step "7/7  Starting the stack"

cd "$PROJECT_DIR"
docker compose --env-file "$ENV_FILE" pull --quiet || true
docker compose --env-file "$ENV_FILE" up -d --build
ok "containers running"

# Quick health check
sleep 5
if curl -fsS --max-time 5 "https://$DOMAIN/api/healthz" >/dev/null 2>&1; then
    ok "https://$DOMAIN responds ✓"
else
    warn "https://$DOMAIN did not respond yet — it may still be warming up."
    echo "Check logs: docker compose logs -f"
fi

# ---------- done ----------
cat <<EOF

${GREEN}═══════════════════════════════════════════════════════════════${RESET}
${GREEN}✓ Installation complete${RESET}
${GREEN}═══════════════════════════════════════════════════════════════${RESET}

  License server:     ${BOLD}https://$DOMAIN${RESET}
  Pricing page:       ${BOLD}https://$DOMAIN/pricing${RESET}
  Stripe webhook URL: ${BOLD}https://$DOMAIN/api/webhook/stripe${RESET}

${BOLD}Next steps:${RESET}

  ${CYAN}1.${RESET} Edit ${BOLD}$ENV_FILE${RESET} and paste your real Stripe keys:
         STRIPE_SECRET_KEY=sk_live_...
         STRIPE_WEBHOOK_SECRET=whsec_...   (from the webhook you create below)

  ${CYAN}2.${RESET} In the Stripe dashboard → Developers → Webhooks, add an endpoint:
         URL:    https://$DOMAIN/api/webhook/stripe
         Events: checkout.session.completed, invoice.paid,
                 customer.subscription.deleted, customer.subscription.updated
         Copy the 'Signing secret' into STRIPE_WEBHOOK_SECRET in .env

  ${CYAN}3.${RESET} Restart the stack to apply new env values:
         cd $PROJECT_DIR && docker compose --env-file .env restart backend

  ${CYAN}4.${RESET} (Optional) Adjust product prices / IP-change limits in:
         $PROJECT_DIR/backend/config.py
         Then:  docker compose --env-file .env restart backend

${BOLD}Useful commands:${RESET}
  docker compose logs -f backend      ${DIM}# tail backend logs${RESET}
  docker compose restart              ${DIM}# restart all services${RESET}
  docker compose down                 ${DIM}# stop everything${RESET}
  docker compose --env-file .env up -d ${DIM}# start again${RESET}

EOF
