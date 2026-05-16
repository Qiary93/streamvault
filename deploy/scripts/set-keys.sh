#!/usr/bin/env bash
# =============================================================================
# StreamVault — interactive helper to update Stripe + License keys post-install.
# -----------------------------------------------------------------------------
# Usage:
#   sudo bash deploy/scripts/set-keys.sh                # interactive prompts
#   sudo bash deploy/scripts/set-keys.sh --show         # print current values (masked)
#   sudo bash deploy/scripts/set-keys.sh --license=SVL-XXXXX-... # non-interactive
#
# Edits /opt/streamvault/deploy/.env (or wherever you cloned it) and restarts
# the backend container. The StreamVault backend reads these env vars at boot
# via docker-compose `env_file:` — there's no separate /app/backend/.env.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"

C_CYAN='\033[1;36m'; C_GREEN='\033[1;32m'; C_YEL='\033[1;33m'; C_RED='\033[1;31m'
C_BOLD='\033[1m';    C_DIM='\033[2m';      C_RESET='\033[0m'

log()  { printf "${C_CYAN}▸${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YEL}!${C_RESET} %s\n" "$*" >&2; }
die()  { printf "${C_RED}✗${C_RESET} %s\n" "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root (use sudo)."
[[ -f "$ENV_FILE" ]] || die "Missing $ENV_FILE. Have you run the installer yet?"

# Parse args
MODE=interactive
NEW_STRIPE=""
NEW_WEBHOOK=""
NEW_LICENSE=""
for arg in "$@"; do
    case "$arg" in
        --show|-s)            MODE=show ;;
        --stripe=*)           MODE=set; NEW_STRIPE="${arg#--stripe=}" ;;
        --webhook=*)          MODE=set; NEW_WEBHOOK="${arg#--webhook=}" ;;
        --license=*)          MODE=set; NEW_LICENSE="${arg#--license=}" ;;
        -h|--help)
            sed -n '2,12p' "$0" | sed 's/^# \?//'
            exit 0 ;;
        *) die "Unknown argument: $arg" ;;
    esac
done

get_val() { grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d= -f2- ; }
mask() {
    local v="$1"
    if [[ -z "$v" ]]; then echo "${C_DIM}(not set)${C_RESET}"; return; fi
    if [[ ${#v} -le 12 ]]; then echo "${v:0:4}••••"; return; fi
    echo "${v:0:6}••••••••${v: -4}"
}

set_env_value() {
    local var="$1" value="$2"
    if grep -q "^${var}=" "$ENV_FILE"; then
        local esc; esc=$(printf '%s' "$value" | sed 's:[\\/&|]:\\&:g')
        sed -i "s|^${var}=.*|${var}=${esc}|" "$ENV_FILE"
    else
        echo "${var}=${value}" >> "$ENV_FILE"
    fi
}

prompt_value() {
    # prompt_value VAR_NAME "Friendly label" "Help text"
    local var="$1" label="$2" help="$3"
    local current; current="$(get_val "$var")"
    printf "\n${C_BOLD}%s${C_RESET}\n" "$label"
    [[ -n "$help" ]] && printf "${C_DIM}%s${C_RESET}\n" "$help"
    if [[ -n "$current" ]]; then
        printf "  current: %b\n" "$(mask "$current")"
    fi
    printf "  new value (blank = keep current, '-' = clear):\n  > "
    local value=""
    read -r value || true
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    if [[ -z "$value" ]]; then
        printf "  ${C_DIM}(unchanged)${C_RESET}\n"
        return
    fi
    if [[ "$value" == "-" ]]; then
        set_env_value "$var" ""
        printf "  ${C_GREEN}cleared${C_RESET}\n"
        return
    fi
    set_env_value "$var" "$value"
    printf "  ${C_GREEN}✓ saved${C_RESET}\n"
}

show_current() {
    printf "${C_CYAN}═══ Current values in %s ═══${C_RESET}\n" "$ENV_FILE"
    printf "  %-32s %b\n" "STRIPE_API_KEY"                "$(mask "$(get_val STRIPE_API_KEY)")"
    printf "  %-32s %b\n" "STRIPE_CONNECT_WEBHOOK_SECRET" "$(mask "$(get_val STRIPE_CONNECT_WEBHOOK_SECRET)")"
    printf "  %-32s %b\n" "STREAMVAULT_LICENSE_KEY"       "$(mask "$(get_val STREAMVAULT_LICENSE_KEY)")"
    printf "  %-32s %s\n" "LICENSE_SERVER_URL"            "$(get_val LICENSE_SERVER_URL)"
    printf "  %-32s %s\n" "ENFORCE_LICENSE"               "$(get_val ENFORCE_LICENSE)"
}

restart_backend() {
    if ! command -v docker >/dev/null 2>&1; then
        warn "docker not installed — skipping restart."
        return
    fi
    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^sv-backend$'; then
        warn "sv-backend not running — nothing to restart. Run install.sh to bring the stack up."
        return
    fi
    log "Restarting sv-backend so it picks up the new env vars…"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d backend >/dev/null
    sleep 2
    ok "sv-backend restarted"
}

case "$MODE" in
    show)
        show_current
        ;;
    set)
        # Non-interactive (CI-style)
        [[ -n "$NEW_STRIPE" ]]   && { set_env_value STRIPE_API_KEY                "$NEW_STRIPE";   ok "STRIPE_API_KEY updated"; }
        [[ -n "$NEW_WEBHOOK" ]]  && { set_env_value STRIPE_CONNECT_WEBHOOK_SECRET "$NEW_WEBHOOK";  ok "STRIPE_CONNECT_WEBHOOK_SECRET updated"; }
        [[ -n "$NEW_LICENSE" ]]  && { set_env_value STREAMVAULT_LICENSE_KEY       "$NEW_LICENSE";  ok "STREAMVAULT_LICENSE_KEY updated"; }
        restart_backend
        ;;
    interactive)
        printf "${C_BOLD}${C_CYAN}\n"
        printf "═══════════════════════════════════════════════════════════════\n"
        printf "  StreamVault — Stripe + License key editor\n"
        printf "═══════════════════════════════════════════════════════════════${C_RESET}\n"
        printf "${C_DIM}For each prompt: press Enter to keep the current value, type '-' to clear, or paste a new value.${C_RESET}\n"

        prompt_value STRIPE_API_KEY \
            "Stripe secret API key" \
            "From https://dashboard.stripe.com/apikeys. Starts with sk_live_… or sk_test_…"

        prompt_value STRIPE_CONNECT_WEBHOOK_SECRET \
            "Stripe Connect webhook signing secret" \
            "Stripe → Developers → Webhooks → /api/webhook/stripe/connect → Signing secret. Starts with whsec_…"

        prompt_value STREAMVAULT_LICENSE_KEY \
            "StreamVault License code" \
            "Buy / retrieve from https://license.stream-vault.eu/dashboard."

        echo
        restart_backend
        echo
        show_current
        ;;
esac
