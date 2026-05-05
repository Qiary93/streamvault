"""Stripe Checkout session creation + status polling."""
from __future__ import annotations

from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from config import CURRENCY, PRODUCTS, STRIPE_SECRET_KEY
from db import db
from models import CheckoutRequest, CheckoutResponse, CheckoutStatusResponse

stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/checkout", tags=["checkout"])


def _to_cents(amount: float) -> int:
    return int(round(amount * 100))


@router.post("/create", response_model=CheckoutResponse)
async def create_checkout_session(
    body: CheckoutRequest,
    user: dict = Depends(get_current_user),
):
    product = PRODUCTS.get(body.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Unknown product")

    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/pricing?cancelled=1"

    # Make sure we have a Stripe customer for this user (so subscriptions work).
    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            name=user.get("full_name") or None,
            metadata={"user_id": user["user_id"]},
        )
        customer_id = customer.id
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    # Build the line item with `price_data` (dynamic price — no Stripe Price ID needed,
    # so the seller can change prices in config.py without touching Stripe).
    if product["mode"] == "payment":
        line_item = {
            "price_data": {
                "currency": CURRENCY,
                "product_data": {
                    "name": product["name"],
                    "description": product["description"],
                },
                "unit_amount": _to_cents(product["price"]),
            },
            "quantity": 1,
        }
    elif product["mode"] == "subscription":
        line_item = {
            "price_data": {
                "currency": CURRENCY,
                "product_data": {
                    "name": product["name"],
                    "description": product["description"],
                },
                "unit_amount": _to_cents(product["price"]),
                "recurring": {"interval": product["interval"] or "month"},
            },
            "quantity": 1,
        }
    else:
        raise HTTPException(status_code=500, detail=f"Bad product mode: {product['mode']}")

    session = stripe.checkout.Session.create(
        mode=product["mode"],
        customer=customer_id,
        line_items=[line_item],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user["user_id"],
            "product_id": product["id"],
        },
        # On subscription mode, also propagate metadata to the subscription itself.
        subscription_data={
            "metadata": {
                "user_id": user["user_id"],
                "product_id": product["id"],
            }
        } if product["mode"] == "subscription" else None,
    )

    # Record the pending transaction BEFORE redirecting (mandatory).
    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": user["user_id"],
        "product_id": product["id"],
        "amount": product["price"],
        "currency": CURRENCY,
        "mode": product["mode"],
        "status": "pending",
        "payment_status": "unpaid",
        "license_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

    return CheckoutResponse(checkout_url=session.url, session_id=session.id)


@router.get("/status/{session_id}", response_model=CheckoutStatusResponse)
async def checkout_status(session_id: str, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"_id": 0},
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Session not found")

    # If the webhook already finalized it, just return what we have.
    if tx["status"] in ("paid", "failed", "expired"):
        license_key = None
        if tx.get("license_id"):
            lic = await db.licenses.find_one({"license_id": tx["license_id"]}, {"_id": 0, "license_key": 1})
            if lic:
                license_key = lic["license_key"]
        return CheckoutStatusResponse(
            session_id=session_id,
            status=tx["status"],
            payment_status=tx["payment_status"],
            license_key=license_key,
            product_id=tx["product_id"],
        )

    # Otherwise, poll Stripe directly (in case the webhook is delayed).
    session = stripe.checkout.Session.retrieve(session_id)
    payment_status = session.payment_status or "unpaid"
    if payment_status == "paid":
        # The webhook handler is idempotent and will create the license.
        # We don't duplicate that work here — just report.
        return CheckoutStatusResponse(
            session_id=session_id,
            status="pending",       # webhook hasn't finalized yet
            payment_status=payment_status,
            license_key=None,
            product_id=tx["product_id"],
        )
    return CheckoutStatusResponse(
        session_id=session_id,
        status="pending",
        payment_status=payment_status,
        license_key=None,
        product_id=tx["product_id"],
    )
