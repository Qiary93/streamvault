"""
DramaroSub License Server — central configuration.

⭐ THIS IS THE FILE YOU EDIT TO CHANGE PRICES, DOMAIN, OR STRIPE KEYS. ⭐

Anything sensitive (Stripe keys, JWT secret) lives in `.env`. Everything else
(prices, product names, IP-change rate limit, license-key prefix, affiliate
commission, etc.) lives here as plain Python.

After editing, restart the backend:  `docker compose restart backend`
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


# =====================================================================
# 🌐 DOMAIN / PUBLIC URL
# =====================================================================
LICENSE_SERVER_DOMAIN = os.environ.get("FRONTEND_URL", "https://license.stream-vault.eu")

CORS_ORIGINS = [
    LICENSE_SERVER_DOMAIN,
    "http://localhost:3001",
    "http://localhost:3000",
]


# =====================================================================
# 💳 STRIPE
# =====================================================================
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

CURRENCY = "usd"


# =====================================================================
# 💰 PRODUCTS / PRICING — change anytime, restart backend
# =====================================================================
# Each product has:
#   id          — short slug used in URLs and DB (don't change once sold)
#   name        — displayed on pricing page + checkout
#   description — appears on Stripe checkout page
#   price       — DECIMAL in USD (e.g. 1500.00). Stripe gets this in cents.
#   mode        — "payment" (one-time) or "subscription" (recurring)
#   interval    — "month" or "year" (only for subscriptions)
#   tier        — "basic" | "pro" | "enterprise" (groups monthly + annual together)
#   features    — list[str] shown on pricing page
#   highlight   — bool, true = "Most Popular" badge on pricing page
#
# 💡 Tip: annual tiers commonly offer ~17% off (2 months free). Adjust to taste.

PRODUCTS = {
    # --- Basic (one-time) ---
    "basic": {
        "id": "basic",
        "tier": "basic",
        "name": "Basic",
        "description": "StreamVault Basic License — lifetime, single server.",
        "price": 1500.00,
        "mode": "payment",
        "interval": None,
        "features": [
            "Lifetime license, no recurring fees",
            "Single VPS / single IP",
            "All viewer + streamer features",
            "Stripe + LiveKit + SMTP integrations",
            "Community support (GitHub issues)",
            "Updates for 1 year",
        ],
        "highlight": False,
    },
    # --- Pro ---
    "pro": {
        "id": "pro",
        "tier": "pro",
        "name": "Pro",
        "description": "StreamVault Pro — monthly subscription with auto-updates.",
        "price": 99.00,
        "mode": "subscription",
        "interval": "month",
        "features": [
            "Single VPS / single IP",
            "All Basic features",
            "Lifetime updates (auto-update enabled)",
            "Priority email support (24h response)",
            "Advanced analytics dashboard",
            "Cancel anytime",
        ],
        "highlight": True,
    },
    "pro_annual": {
        "id": "pro_annual",
        "tier": "pro",
        "name": "Pro (Annual)",
        "description": "StreamVault Pro — annual subscription, 2 months free.",
        "price": 990.00,        # $99 × 12 = $1188; save ~17% = $990 (2 months free)
        "mode": "subscription",
        "interval": "year",
        "features": [
            "Everything in Pro (monthly)",
            "🎁 2 months free — $198 saved",
            "Locked-in pricing for 12 months",
        ],
        "highlight": False,
    },
    # --- Enterprise ---
    "enterprise": {
        "id": "enterprise",
        "tier": "enterprise",
        "name": "Enterprise",
        "description": "StreamVault Enterprise — multi-server, premium support.",
        "price": 299.00,
        "mode": "subscription",
        "interval": "month",
        "features": [
            "Multi-server (up to 5 IPs per license)",
            "All Pro features",
            "Priority support (4h response, dedicated channel)",
            "Custom feature requests (1 per quarter)",
            "White-label rights (resell to your clients)",
            "Onboarding call + setup assistance",
        ],
        "highlight": False,
    },
    "enterprise_annual": {
        "id": "enterprise_annual",
        "tier": "enterprise",
        "name": "Enterprise (Annual)",
        "description": "StreamVault Enterprise — annual, 2 months free.",
        "price": 2990.00,        # $299 × 12 = $3588; save ~17% = $2990
        "mode": "subscription",
        "interval": "year",
        "features": [
            "Everything in Enterprise (monthly)",
            "🎁 2 months free — $598 saved",
            "Locked-in pricing for 12 months",
        ],
        "highlight": False,
    },
}


# =====================================================================
# 🔑 LICENSE KEYS
# =====================================================================
LICENSE_KEY_PREFIX = "DSB"
LICENSE_KEY_GROUPS = 4
LICENSE_KEY_GROUP_LEN = 5

VALIDATION_PING_INTERVAL_HOURS = 24
OFFLINE_GRACE_DAYS = 14


# =====================================================================
# 🔄 IP BINDING POLICY (per license)
# =====================================================================
IP_CHANGE_LIMIT_PER_MONTH = 3
IP_CHANGE_WINDOW_DAYS = 30


# =====================================================================
# 🎟️ COUPONS
# =====================================================================
# Coupons are created/edited from the admin dashboard at runtime — this value
# is only the DEFAULT commission for newly created coupons.
COUPON_MAX_DISCOUNT_PERCENT = 90     # safety cap — no 100%-off freebies


# =====================================================================
# 🤝 AFFILIATE PROGRAM
# =====================================================================
# When a customer signs up with ?ref=CODE and later purchases, the affiliate
# earns a commission.
AFFILIATE_DEFAULT_COMMISSION_PERCENT = 20   # % of the sale amount
AFFILIATE_COOKIE_DAYS = 30                  # how long the referral cookie lasts
AFFILIATE_MIN_PAYOUT_USD = 50.0             # affiliates must accrue this much before payout


# =====================================================================
# 📨 EXPIRY WARNINGS
# =====================================================================
# Days before expiry to email the customer.
EXPIRY_WARNING_DAYS = [7, 2]
EXPIRY_CHECK_INTERVAL_HOURS = 12


# =====================================================================
# 🔐 AUTH (JWT)
# =====================================================================
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MINUTES = 15
REFRESH_TOKEN_TTL_DAYS = 30

MIN_PASSWORD_LENGTH = 8


# =====================================================================
# 👤 ADMIN SEEDING
# =====================================================================
# The account with this email will be auto-promoted to admin on startup.
# (Create the account normally via the /register page first.)
ADMIN_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL", "").strip().lower()


# =====================================================================
# 📧 SMTP
# =====================================================================
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@stream-vault.eu")

ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL", "")


# =====================================================================
# 🗄️ DATABASE
# =====================================================================
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "stream_vault_license")
