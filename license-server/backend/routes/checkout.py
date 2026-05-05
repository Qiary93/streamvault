"""Stripe Checkout session creation + status polling.
Handles coupon codes and affiliate attribution."""
from __future__ import annotations

from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from config import CURRENCY, PRODUCTS, STRIPE_SECRET_KEY
from db import db
from models import CheckoutRequest, CheckoutResponse, CheckoutStatusResponse
from routes.coupons import apply_coupon_to_price

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

    # Ensure Stripe customer exists
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

    # Compute final price (may be discounted by a coupon)
    base_price = product["price"]
    final_price, coupon_doc = await apply_coupon_to_price(body.coupon_code, product["id"], base_price)
    discount = round(base_price - final_price, 2)

    # Validate affiliate code (stored on the session for attribution later)
    affiliate_code_upper = body.referral_code.strip().upper() if body.referral_code else None
    affiliate_doc = None
    if affiliate_code_upper:
        affiliate_doc = await db.affiliates.find_one({"code": affiliate_code_upper}, {"_id": 0, "user_id": 1, "code": 1})
        if affiliate_doc and affiliate_doc["user_id"] == user["user_id"]:
            affiliate_doc = None  # self-referrals not allowed

    # Build line item with dynamic price_data (no Stripe Price IDs to manage)
    product_data = {
        "name": product["name"] + (f" (coupon {coupon_doc['code']})" if coupon_doc else ""),
        "description": product["description"],
    }
    if product["mode"] == "payment":
        line_item = {
            "price_data": {
                "currency": CURRENCY,
                "product_data": product_data,
                "unit_amount": _to_cents(final_price),
            },
            "quantity": 1,
        }
    elif product["mode"] == "subscription":
        line_item = {
            "price_data": {
                "currency": CURRENCY,
                "product_data": product_data,
                "unit_amount": _to_cents(final_price),
                "recurring": {"interval": product["interval"] or "month"},
            },
            "quantity": 1,
        }
    else:
        raise HTTPException(status_code=500, detail=f"Bad product mode: {product['mode']}")

    metadata = {
        "user_id": user["user_id"],
        "product_id": product["id"],
        "base_price": f"{base_price:.2f}",
        "final_price": f"{final_price:.2f}",
    }
    if coupon_doc:
        metadata["coupon_code"] = coupon_doc["code"]
    if affiliate_doc:
        metadata["affiliate_code"] = affiliate_doc["code"]

    session_kwargs = dict(
        mode=product["mode"],
        customer=customer_id,
        line_items=[line_item],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    if product["mode"] == "subscription":
        session_kwargs["subscription_data"] = {"metadata": metadata}

    session = stripe.checkout.Session.create(**session_kwargs)

    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": user["user_id"],
        "product_id": product["id"],
        "amount": final_price,
        "base_amount": base_price,
        "discount_amount": discount,
        "coupon_code": coupon_doc["code"] if coupon_doc else None,
        "affiliate_code": affiliate_doc["code"] if affiliate_doc else None,
        "currency": CURRENCY,
        "mode": product["mode"],
        "status": "pending",
        "payment_status": "unpaid",
        "license_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

    return CheckoutResponse(
        checkout_url=session.url,
        session_id=session.id,
        discount_applied=discount,
        final_amount=final_price,
    )


@router.get("/status/{session_id}", response_model=CheckoutStatusResponse)
async def checkout_status(session_id: str, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"_id": 0},
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Session not found")

    if tx["status"] in ("paid", "failed", "expired", "refunded"):
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

    session = stripe.checkout.Session.retrieve(session_id)
    return CheckoutStatusResponse(
        session_id=session_id,
        status="pending",
        payment_status=session.payment_status or "unpaid",
        license_key=None,
        product_id=tx["product_id"],
    )
