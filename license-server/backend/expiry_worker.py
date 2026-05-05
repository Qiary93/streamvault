"""Background task — email customers when their subscription is about to expire."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from config import EXPIRY_CHECK_INTERVAL_HOURS, EXPIRY_WARNING_DAYS, LICENSE_SERVER_DOMAIN, PRODUCTS
from db import db
from email_service import send_email, tpl_expiry_warning

logger = logging.getLogger("expiry")


async def _check_once() -> None:
    """Send warnings for licenses expiring within N days (per config.EXPIRY_WARNING_DAYS)."""
    now = datetime.now(timezone.utc)
    # Grab the largest warning window and iterate all active licenses that fall inside it.
    max_window_days = max(EXPIRY_WARNING_DAYS)
    cutoff = now + timedelta(days=max_window_days)

    cur = db.licenses.find(
        {
            "status": "active",
            "expires_at": {"$ne": None, "$lte": cutoff, "$gt": now},
        },
        {"_id": 0},
    )
    count = 0
    async for lic in cur:
        expires = lic.get("expires_at")
        if not isinstance(expires, datetime):
            continue
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        days_left = (expires - now).days
        if days_left not in EXPIRY_WARNING_DAYS:
            continue

        last_sent = lic.get("renewal_warning_sent_at")
        if last_sent and (now - last_sent) < timedelta(hours=20):
            continue   # already warned within the last ~day

        user = await db.users.find_one({"user_id": lic["user_id"]}, {"_id": 0})
        if not user:
            continue

        product = PRODUCTS.get(lic["product_id"], {})
        subject, html = tpl_expiry_warning(
            full_name=user.get("full_name") or "",
            product_name=product.get("name", lic["product_id"]),
            days_left=days_left,
            renew_url=f"{LICENSE_SERVER_DOMAIN}/dashboard",
        )
        if await send_email(user["email"], subject, html):
            await db.licenses.update_one(
                {"license_id": lic["license_id"]},
                {"$set": {"renewal_warning_sent_at": now}},
            )
            count += 1
    if count:
        logger.info(f"Sent {count} expiry warning email(s)")


async def run_loop() -> None:
    await asyncio.sleep(30)   # grace period after startup
    while True:
        try:
            await _check_once()
        except Exception as e:
            logger.exception(f"Expiry check loop error: {e}")
        await asyncio.sleep(EXPIRY_CHECK_INTERVAL_HOURS * 3600)
