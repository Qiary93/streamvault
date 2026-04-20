#!/usr/bin/env bash
# =============================================================================
# StreamVault — one-line VPS bootstrapper
# -----------------------------------------------------------------------------
# Usage (on a fresh Ubuntu 24.04 VPS, as root):
#
#   curl -fsSL https://raw.githubusercontent.com/Qiary93/streamvault/main/deploy/scripts/bootstrap.sh | sudo bash
#
# What it does:
#   1. Installs git + curl + openssl
#   2. Clones https://github.com/Qiary93/streamvault.git into /opt/streamvault
#   3. Prompts you interactively for DOMAIN, email, admin password, optional
#      integration keys — auto-generates JWT_SECRET
#   4. Writes deploy/.env and runs deploy/scripts/install.sh
#
# Re-running is safe — the script detects an existing /opt/streamvault and
# offers to update-in-place instead of re-cloning.
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/Qiary93/streamvault.git"
INSTALL_DIR="/opt/streamvault"
ENV_FILE="$INSTALL_DIR/deploy/.env"

C_CYAN='\033[1;36m'; C_YEL='\033[1;33m'; C_RED='\033[1;31m'; C_GREEN='\033[1;32m'; C_RESET='\033[0m'
log()  { printf "${C_CYAN}[bootstrap]${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_GREEN}[ok]${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YEL}[warn]${C_RESET} %s\n" "$*" >&2; }
die()  { printf "${C_RED}[error]${C_RESET} %s\n" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run this script as root (use sudo)."

# -----------------------------------------------------------------------------
# Step 1 — OS check + baseline tools
# -----------------------------------------------------------------------------
log "Verifying Ubuntu + installing baseline tools (git, curl, openssl)…"
. /etc/os-release
[[ "$ID" == "ubuntu" ]] || warn "This script targets Ubuntu 24.04. Detected: $ID $VERSION_ID"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl openssl ca-certificates >/dev/null
ok "Baseline tools ready."

# -----------------------------------------------------------------------------
# Step 2 — Clone or update the repo
# -----------------------------------------------------------------------------
if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Existing checkout detected at $INSTALL_DIR"
    printf "${C_YEL}?${C_RESET} Pull latest changes from %s ? [Y/n] " "$REPO_URL"
    read -r ans </dev/tty
    if [[ -z "$ans" || "$ans" == [yY]* ]]; then
        git -C "$INSTALL_DIR" pull --ff-only
        ok "Repository updated."
    else
        log "Keeping existing checkout as-is."
    fi
else
    log "Cloning $REPO_URL → $INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    ok "Repository cloned."
fi

cd "$INSTALL_DIR"

# If .env.example is missing (e.g. repo pushed before it was tracked, or
# git-ignored by an overly broad rule), regenerate it from a built-in fallback.
if [[ ! -f "deploy/.env.example" ]]; then
    warn "deploy/.env.example missing in the repo — regenerating a local copy."
    mkdir -p deploy
    cat > deploy/.env.example <<'ENVEXAMPLE'
# StreamVault — production environment configuration
DOMAIN=streamvault.example.com
LETSENCRYPT_EMAIL=admin@example.com
DB_NAME=streamvault
JWT_SECRET=CHANGE_ME_generate_with_openssl_rand_hex_48
ADMIN_EMAIL=admin@streamvault.local
ADMIN_PASSWORD=CHANGE_ME_Strong_Password!
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
LIVEKIT_URL=
STRIPE_API_KEY=
STRIPE_CONNECT_WEBHOOK_SECRET=
ENVEXAMPLE
    ok "Regenerated deploy/.env.example"
fi

[[ -f "deploy/scripts/install.sh" ]] || die "deploy/scripts/install.sh missing in the repo — wrong branch?"

# -----------------------------------------------------------------------------
# Step 3 — Interactive prompts for required env vars
# -----------------------------------------------------------------------------
prompt() {
    # prompt <var_name> <question> [default] [secret=0|1]
    local __varname="$1" __question="$2" __default="${3:-}" __secret="${4:-0}"
    local __input=""
    while true; do
        if [[ "$__secret" == "1" ]]; then
            printf "${C_YEL}?${C_RESET} %s: " "$__question" >&2
            read -rs __input </dev/tty; printf "\n" >&2
        else
            if [[ -n "$__default" ]]; then
                printf "${C_YEL}?${C_RESET} %s [%s]: " "$__question" "$__default" >&2
            else
                printf "${C_YEL}?${C_RESET} %s: " "$__question" >&2
            fi
            read -r __input </dev/tty
        fi
        __input="${__input:-$__default}"
        [[ -n "$__input" ]] && break
        warn "This field is required."
    done
    printf -v "$__varname" "%s" "$__input"
}

ask_yesno() {
    # ask_yesno <var_name> <question> <default=y|n>
    local __var="$1" __q="$2" __def="${3:-n}" __ans=""
    local hint="[y/N]"; [[ "$__def" == "y" ]] && hint="[Y/n]"
    printf "${C_YEL}?${C_RESET} %s %s " "$__q" "$hint" >&2
    read -r __ans </dev/tty
    __ans="${__ans:-$__def}"
    if [[ "$__ans" == [yY]* ]]; then printf -v "$__var" "%s" "yes"
    else printf -v "$__var" "%s" "no"; fi
}

echo
echo "============================================================"
echo "  StreamVault — interactive configuration"
echo "============================================================"
echo "  Required fields have no default. Press Enter to accept the"
echo "  default (shown in [brackets]) when available."
echo

# If .env already exists, offer to reuse
REUSE_ENV="no"
if [[ -f "$ENV_FILE" ]]; then
    ask_yesno REUSE_ENV "An existing deploy/.env was found. Keep it and skip prompts?" "n"
fi

if [[ "$REUSE_ENV" == "yes" ]]; then
    log "Reusing existing $ENV_FILE"
else
    prompt DOMAIN            "Public domain (A-record must point to this server, e.g. stream.example.com)"
    prompt LETSENCRYPT_EMAIL "Email for Let's Encrypt notifications"
    prompt ADMIN_EMAIL       "Admin account email" "admin@${DOMAIN}"
    prompt ADMIN_PASSWORD    "Admin account password (min 8 chars)" "" 1
    [[ ${#ADMIN_PASSWORD} -ge 8 ]] || die "Admin password must be at least 8 characters."

    # Optional integration keys
    echo
    echo "--- Optional third-party keys (press Enter to skip; configure later in .env) ---"
    prompt LIVEKIT_API_KEY       "LiveKit API Key"     " " 0;   [[ "$LIVEKIT_API_KEY" == " " ]] && LIVEKIT_API_KEY=""
    prompt LIVEKIT_API_SECRET    "LiveKit API Secret"  " " 1;   [[ "$LIVEKIT_API_SECRET" == " " ]] && LIVEKIT_API_SECRET=""
    prompt LIVEKIT_URL           "LiveKit URL (wss://…)" " " 0; [[ "$LIVEKIT_URL" == " " ]] && LIVEKIT_URL=""
    prompt STRIPE_API_KEY        "Stripe secret key (sk_…)" " " 1; [[ "$STRIPE_API_KEY" == " " ]] && STRIPE_API_KEY=""
    prompt STRIPE_CONNECT_WEBHOOK_SECRET "Stripe Connect webhook signing secret" " " 1
    [[ "$STRIPE_CONNECT_WEBHOOK_SECRET" == " " ]] && STRIPE_CONNECT_WEBHOOK_SECRET=""

    JWT_SECRET="$(openssl rand -hex 48)"
    log "Generated JWT_SECRET (48 random bytes)."

    # -----------------------------------------------------------------------------
    # Step 4 — Confirm + write .env
    # -----------------------------------------------------------------------------
    echo
    echo "------------- Review -------------"
    echo " Domain:          $DOMAIN"
    echo " LE email:        $LETSENCRYPT_EMAIL"
    echo " Admin email:     $ADMIN_EMAIL"
    echo " Admin password:  (hidden, ${#ADMIN_PASSWORD} chars)"
    echo " LiveKit keys:    $([[ -n $LIVEKIT_API_KEY ]] && echo 'provided' || echo 'empty')"
    echo " Stripe key:      $([[ -n $STRIPE_API_KEY ]] && echo 'provided' || echo 'empty')"
    echo "----------------------------------"
    ask_yesno CONFIRM "Continue with these values?" "y"
    [[ "$CONFIRM" == "yes" ]] || die "Aborted by operator — re-run the command to try again."

    install -m 600 /dev/null "$ENV_FILE"
    cat > "$ENV_FILE" <<EOF
# Generated by deploy/scripts/bootstrap.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
DOMAIN=$DOMAIN
LETSENCRYPT_EMAIL=$LETSENCRYPT_EMAIL
DB_NAME=streamvault
JWT_SECRET=$JWT_SECRET
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$ADMIN_PASSWORD

LIVEKIT_API_KEY=$LIVEKIT_API_KEY
LIVEKIT_API_SECRET=$LIVEKIT_API_SECRET
LIVEKIT_URL=$LIVEKIT_URL

STRIPE_API_KEY=$STRIPE_API_KEY
STRIPE_CONNECT_WEBHOOK_SECRET=$STRIPE_CONNECT_WEBHOOK_SECRET
EOF
    chmod 600 "$ENV_FILE"
    ok "Wrote $ENV_FILE (chmod 600)."
fi

# -----------------------------------------------------------------------------
# Step 5 — Run the main installer
# -----------------------------------------------------------------------------
echo
log "Handing off to deploy/scripts/install.sh (Docker + SSL + stack + systemd)…"
bash "$INSTALL_DIR/deploy/scripts/install.sh"
