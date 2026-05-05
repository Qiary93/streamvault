"""
DramaroSub License Server — central configuration.

⭐ THIS IS THE FILE YOU EDIT TO CHANGE PRICES, DOMAIN, OR STRIPE KEYS. ⭐

Anything sensitive (Stripe keys, JWT secret) lives in `.env`. Everything else
(prices, product names, IP-change rate limit, license-key prefix) lives here
as plain Python so you can change it without touching the database or Stripe
dashboard.

After editing, restart the backend:  `docker compose restart backend`
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env (sits next to this file)
load_dotenv(Path(__file__).parent / ".env")


# =====================================================================
# 🌐 DOMAIN / PUBLIC URL
# =====================================================================
# The public URL of the license-server frontend. Used to build Stripe
# success/cancel URLs and the email "view your license" links.
LICENSE_SERVER_DOMAIN = os.environ.get("FRONTEND_URL", "https://dramarosub.ro")

# CORS — origins allowed to hit our API. Add staging URLs here as needed.
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

# Default currency for all checkouts. Stripe formats this in customer's locale.
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
#   features    — list[str] shown on pricing page
#   highlight   — bool, true = "Most Popular" badge on pricing page

PRODUCTS = {
    "basic": {
        "id": "basic",
        "name": "Basic",
        "description": "StreamVault Basic License — lifetime, single server.",
        "price": 1500.00,
        "mode": "payment",        # one-time
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
    "pro": {
        "id": "pro",
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
        "highlight": True,         # ← "Most Popular"
    },
    "enterprise": {
        "id": "enterprise",
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
}


# =====================================================================
# 🔑 LICENSE KEYS
# =====================================================================
# Prefix shown on every key. Keep short and recognizable.
# Example output: DSB-A2K9F-7XW3R-PQM4D-NHJV8
LICENSE_KEY_PREFIX = "DSB"
LICENSE_KEY_GROUPS = 4         # number of 5-char groups after the prefix
LICENSE_KEY_GROUP_LEN = 5

# How often the buyer's StreamVault install pings us to revalidate.
# (We just suggest this in the buyer-side code — it's not enforced server-side.)
VALIDATION_PING_INTERVAL_HOURS = 24

# Grace period if the license server is unreachable from the buyer's VPS.
# (Documented for the buyer-side code. Not enforced here.)
OFFLINE_GRACE_DAYS = 14


# =====================================================================
# 🔄 IP BINDING POLICY (per license)
# =====================================================================
# Customers can self-service change their bound IP from the dashboard.
# This guards against the same key being shared across many servers.
IP_CHANGE_LIMIT_PER_MONTH = 3
IP_CHANGE_WINDOW_DAYS = 30


# =====================================================================
# 🔐 AUTH (JWT)
# =====================================================================
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MINUTES = 15
REFRESH_TOKEN_TTL_DAYS = 30

# Min password length on registration / change.
MIN_PASSWORD_LENGTH = 8


# =====================================================================
# 📧 SMTP (optional — used for license-issued / expiry-warning emails)
# =====================================================================
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@dramarosub.ro")

# Where to email new-sale notifications. Blank = disabled.
ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL", "")


# =====================================================================
# 🗄️ DATABASE
# =====================================================================
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "dramarosub_license")
