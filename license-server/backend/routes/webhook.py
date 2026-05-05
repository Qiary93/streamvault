"""Stripe webhook handler — single source of truth for license issuance,
coupon-usage tracking, affiliate commission crediting, and email notifications."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, HTTPException, Request

from config import ADMIN_NOTIFY_EMAIL, PRODUCTS, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET
from db import db
from email_service import send_email, tpl_admin_sale, tpl_license_issued
from license_keys import generate_license_key, new_license_id
from routes.affiliates import record_affiliate_sale
from routes.coupons import increment_coupon_usage

stripe.api_key = STRIPE_SECRET_KEY
logger = logging.getLogger("webhook")

router = APIRouter(prefix="/api/webhook", tags=["webhook"])


async def _issue_license(
    user_id: str, product_id: str, session_id: str,
    subscription_id: str | None, amount_paid: float,
    coupon_code: str | None, affiliate_code: str | None,
) -> str:
    """Idempotent — returns existing license_id if this session already has one."""
    existing_tx = await db.payment_transactions.find_one(
        {"session_id": session_id}, {"_id": 0, "license_id": 1}
    )
    if existing_tx and existing_tx.get("license_id"):
        return existing_tx["license_id"]

    product = PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=400, detail=f"Unknown product: {product_id}")

    max_ips = 5 if product_id.startswith("enterprise") else 1
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
        "expires_at": None,
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

    if coupon_code:
        await increment_coupon_usage(coupon_code)

    if affiliate_code:
        await record_affiliate_sale(
            affiliate_code=affiliate_code,
            buyer_user_id=user_id,
            license_id=license_doc["license_id"],
            product_id=product_id,
            amount=amount_paid,
        )

    # Email the buyer
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if user:
        renews_at = None
        if product["mode"] == "subscription" and subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
                renews_at = end.strftime("%B %d, %Y")
            except Exception:
                renews_at = None
        subject, html = tpl_license_issued(
            full_name=user.get("full_name") or "",
            product_name=product["name"],
            license_key=license_doc["license_key"],
            mode=product["mode"],
            renews_at=renews_at,
        )
        await send_email(user["email"], subject, html)

        # Notify the site admin
        if ADMIN_NOTIFY_EMAIL:
            admin_subject, admin_html = tpl_admin_sale(
                product_name=product["name"],
                amount=amount_paid,
                customer_email=user["email"],
                coupon=coupon_code,
                affiliate=affiliate_code,
            )
            await send_email(ADMIN_NOTIFY_EMAIL, admin_subject, admin_html)

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
        meta = obj.get("metadata") or {}
        user_id = meta.get("user_id")
        product_id = meta.get("product_id")
        subscription_id = obj.get("subscription")
        if user_id and product_id and obj.get("payment_status") == "paid":
            amount_paid = float(meta.get("final_price") or (obj.get("amount_total", 0) / 100.0))
            await _issue_license(
                user_id=user_id,
                product_id=product_id,
                session_id=session_id,
                subscription_id=subscription_id,
                amount_paid=amount_paid,
                coupon_code=meta.get("coupon_code"),
                affiliate_code=meta.get("affiliate_code"),
            )

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
        subscription_id = obj.get("subscription")
        if subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                current_period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
            except Exception as e:
                logger.warning(f"Could not retrieve subscription {subscription_id}: {e}")
                current_period_end = None
            update = {"status": "active", "updated_at": datetime.now(timezone.utc)}
            if current_period_end:
                update["expires_at"] = current_period_end
            update["renewal_warning_sent_at"] = None   # reset so warnings fire next cycle
            await db.licenses.update_many(
                {"stripe_subscription_id": subscription_id},
                {"$set": update},
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
