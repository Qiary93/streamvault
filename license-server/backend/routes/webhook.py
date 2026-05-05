"""Stripe webhook handler — single source of truth for license issuance."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request

from config import PRODUCTS, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from db import db
from license_keys import generate_license_key, new_license_id

stripe.api_key = STRIPE_SECRET_KEY
logger = logging.getLogger("webhook")

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


async def _issue_license(user_id: str, product_id: str, session_id: str, subscription_id: str | None = None) -> str:
    """Idempotent — returns existing license_id if this session already has one."""
    existing_tx = await db.payment_transactions.find_one(
        {"session_id": session_id}, {"_id": 0, "license_id": 1}
    )
    if existing_tx and existing_tx.get("license_id"):
        return existing_tx["license_id"]

    product = PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=400, detail=f"Unknown product: {product_id}")

    max_ips = 5 if product_id == "enterprise" else 1
    license_doc = {
        "license_id": new_license_id(),
        "license_key": generate_license_key(),
        "user_id": user_id,
        "product_id": product_id,
        "status": "active",
        "bound_ips": [],
        "max_ips": max_ips,
        "stripe_session_id": session_id,
        "stripe_subscription_id": subscription_id,
        "expires_at": None,        # subscriptions get their expiry from Stripe
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.licenses.insert_one(license_doc)
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "status": "paid",
            "payment_status": "paid",
            "license_id": license_doc["license_id"],
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return license_doc["license_id"]


@router.post("/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning(f"Stripe webhook signature failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    etype = event["type"]
    obj = event["data"]["object"]
    logger.info(f"Stripe webhook: {etype}")

    if etype == "checkout.session.completed":
        session_id = obj["id"]
        user_id = (obj.get("metadata") or {}).get("user_id")
        product_id = (obj.get("metadata") or {}).get("product_id")
        subscription_id = obj.get("subscription")
        if user_id and product_id and obj.get("payment_status") == "paid":
            await _issue_license(user_id, product_id, session_id, subscription_id)

            # Track the subscription separately so we can react to renewals/cancels.
            if subscription_id:
                await db.subscriptions.update_one(
                    {"stripe_subscription_id": subscription_id},
                    {"$set": {
                        "user_id": user_id,
                        "product_id": product_id,
                        "stripe_subscription_id": subscription_id,
                        "status": "active",
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }},
                    upsert=True,
                )

    elif etype == "invoice.paid":
        # Recurring payment succeeded — extend the license expiry.
        subscription_id = obj.get("subscription")
        if subscription_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            current_period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
            await db.licenses.update_many(
                {"stripe_subscription_id": subscription_id},
                {"$set": {
                    "status": "active",
                    "expires_at": current_period_end,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )

    elif etype in ("customer.subscription.deleted", "customer.subscription.updated"):
        subscription_id = obj.get("id")
        new_status = obj.get("status", "")
        if etype == "customer.subscription.deleted" or new_status in ("canceled", "incomplete_expired", "unpaid"):
            await db.licenses.update_many(
                {"stripe_subscription_id": subscription_id},
                {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc)}},
            )
            await db.subscriptions.update_one(
                {"stripe_subscription_id": subscription_id},
                {"$set": {"status": new_status or "canceled", "updated_at": datetime.now(timezone.utc)}},
            )
        else:
            await db.subscriptions.update_one(
                {"stripe_subscription_id": subscription_id},
                {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
            )

    return {"received": True}
