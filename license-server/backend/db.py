"""Mongo client + index setup."""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient

from config import DB_NAME, MONGO_URL

client = AsyncIOMotorClient(MONGO_URL, tz_aware=True)
db = client[DB_NAME]


async def ensure_indexes() -> None:
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)

    await db.licenses.create_index("license_key", unique=True)
    await db.licenses.create_index([("user_id", 1), ("created_at", -1)])
    await db.licenses.create_index("status")
    await db.licenses.create_index("expires_at")

    await db.ip_change_log.create_index([("license_id", 1), ("changed_at", -1)])

    await db.payment_transactions.create_index("session_id", unique=True)
    await db.payment_transactions.create_index([("user_id", 1), ("created_at", -1)])
    await db.payment_transactions.create_index("status")

    await db.subscriptions.create_index("stripe_subscription_id", unique=True)
    await db.subscriptions.create_index([("user_id", 1), ("created_at", -1)])

    await db.coupons.create_index("code", unique=True)
    await db.coupons.create_index("active")

    await db.affiliates.create_index("code", unique=True)
    await db.affiliates.create_index("user_id", unique=True)
    await db.affiliate_sales.create_index([("affiliate_id", 1), ("created_at", -1)])
    await db.affiliate_sales.create_index("paid")
