"""Seller admin routes — list users/licenses, revoke, refund, manual issue, stats."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query

from auth import get_admin_user
from config import PRODUCTS, STRIPE_SECRET_KEY
from db import db
from email_service import send_email, tpl_license_revoked
from license_keys import generate_license_key, new_license_id
from models import (
    AdminLicenseListItem,
    AdminManualLicenseRequest,
    AdminRefundRequest,
    AdminRevokeRequest,
    AdminStatsResponse,
    AdminUserResponse,
)

stripe.api_key = STRIPE_SECRET_KEY
logger = logging.getLogger("admin")

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- users ----------

@router.get("/users", response_model=List[AdminUserResponse])
async def list_users(
    admin: dict = Depends(get_admin_user),
    q: Optional[str] = Query(default=None, description="Search email / full_name"),
    limit: int = Query(default=50, le=200),
):
    flt = {}
    if q:
        flt = {"$or": [
            {"email":     {"$regex": q, "$options": "i"}},
            {"full_name": {"$regex": q, "$options": "i"}},
        ]}
    cur = db.users.find(flt, {"_id": 0, "password_hash": 0}).sort("created_at", -1).limit(limit)
    out: List[AdminUserResponse] = []
    async for u in cur:
        lic_count = await db.licenses.count_documents({"user_id": u["user_id"]})
        # Revenue = sum of paid transactions for this user
        pipeline = [
            {"$match": {"user_id": u["user_id"], "status": "paid"}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
        revenue = 0.0
        async for row in db.payment_transactions.aggregate(pipeline):
            revenue = float(row.get("total", 0))
            break
        out.append(AdminUserResponse(
            user_id=u["user_id"],
            email=u["email"],
            full_name=u.get("full_name"),
            is_admin=bool(u.get("is_admin")),
            license_count=lic_count,
            total_spent=round(revenue, 2),
            created_at=u["created_at"],
        ))
    return out


# ---------- licenses ----------

@router.get("/licenses", response_model=List[AdminLicenseListItem])
async def list_all_licenses(
    admin: dict = Depends(get_admin_user),
    status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    flt = {}
    if status:
        flt["status"] = status
    cur = db.licenses.find(flt, {"_id": 0}).sort("created_at", -1).limit(limit)
    out: List[AdminLicenseListItem] = []
    async for lic in cur:
        user = await db.users.find_one({"user_id": lic["user_id"]}, {"_id": 0, "email": 1})
        email = user["email"] if user else "—"
        if q and q.lower() not in email.lower() and q.lower() not in lic["license_key"].lower():
            continue
        out.append(AdminLicenseListItem(
            license_id=lic["license_id"],
            license_key=lic["license_key"],
            user_email=email,
            product_id=lic["product_id"],
            product_name=PRODUCTS.get(lic["product_id"], {}).get("name", lic["product_id"]),
            status=lic["status"],
            bound_ips=lic.get("bound_ips", []),
            expires_at=lic.get("expires_at"),
            created_at=lic["created_at"],
        ))
    return out


@router.post("/licenses/{license_id}/revoke")
async def revoke_license(license_id: str, body: AdminRevokeRequest, admin: dict = Depends(get_admin_user)):
    lic = await db.licenses.find_one({"license_id": license_id}, {"_id": 0})
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    await db.licenses.update_one(
        {"license_id": license_id},
        {"$set": {
            "status": "revoked",
            "revoked_at": datetime.now(timezone.utc),
            "revoked_by": admin["user_id"],
            "revoke_reason": body.reason,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    user = await db.users.find_one({"user_id": lic["user_id"]}, {"_id": 0})
    if user:
        subject, html = tpl_license_revoked(
            user.get("full_name") or "",
            PRODUCTS.get(lic["product_id"], {}).get("name", lic["product_id"]),
            body.reason or "",
        )
        await send_email(user["email"], subject, html)

    # Also cancel any linked Stripe subscription (best-effort)
    sub_id = lic.get("stripe_subscription_id")
    if sub_id:
        try:
            stripe.Subscription.delete(sub_id)
        except Exception as e:
            logger.warning(f"Could not cancel Stripe subscription {sub_id}: {e}")

    return {"ok": True, "license_id": license_id}


@router.post("/licenses/{license_id}/refund")
async def refund_license(license_id: str, body: AdminRefundRequest, admin: dict = Depends(get_admin_user)):
    lic = await db.licenses.find_one({"license_id": license_id}, {"_id": 0})
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    session_id = lic.get("stripe_session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="This license has no linked Stripe session (manual issue?)")

    # Look up the PaymentIntent on the session
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
        pi_id = session.payment_intent if isinstance(session.payment_intent, str) else session.payment_intent.id
        if not pi_id:
            raise HTTPException(status_code=400, detail="No payment_intent found on this session (subscription setup?)")
        refund = stripe.Refund.create(payment_intent=pi_id, reason="requested_by_customer")
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe refund failed: {e.user_message or str(e)}")

    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "status": "refunded",
            "refund_id": refund.id,
            "refund_reason": body.reason,
            "refunded_at": datetime.now(timezone.utc),
        }},
    )

    if body.revoke_license:
        await db.licenses.update_one(
            {"license_id": license_id},
            {"$set": {
                "status": "revoked",
                "revoked_at": datetime.now(timezone.utc),
                "revoke_reason": f"Refunded: {body.reason or ''}",
                "updated_at": datetime.now(timezone.utc),
            }},
        )

    return {"ok": True, "refund_id": refund.id, "revoked": body.revoke_license}


@router.post("/licenses/manual", status_code=201)
async def manual_issue_license(body: AdminManualLicenseRequest, admin: dict = Depends(get_admin_user)):
    """Create a license for a user without running a Stripe checkout.
    Used for customer-support comps, beta testers, etc."""
    product = PRODUCTS.get(body.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Unknown product")

    user = await db.users.find_one({"email": body.user_email.lower()}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="No user with that email — ask them to register first")

    max_ips = 5 if product["id"].startswith("enterprise") else 1
    lic = {
        "license_id": new_license_id(),
        "license_key": generate_license_key(),
        "user_id": user["user_id"],
        "product_id": product["id"],
        "status": "active",
        "bound_ips": [],
        "max_ips": max_ips,
        "stripe_session_id": None,
        "stripe_subscription_id": None,
        "expires_at": body.expires_at,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "manual_issue": True,
        "issued_by": admin["user_id"],
        "issue_note": body.note,
    }
    await db.licenses.insert_one(lic)
    return {"ok": True, "license_id": lic["license_id"], "license_key": lic["license_key"]}


# ---------- stats ----------

@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(admin: dict = Depends(get_admin_user)):
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    total_users = await db.users.count_documents({})
    total_licenses = await db.licenses.count_documents({})
    active_licenses = await db.licenses.count_documents({"status": "active"})
    expired_licenses = await db.licenses.count_documents({"status": "expired"})
    revoked_licenses = await db.licenses.count_documents({"status": "revoked"})

    # Revenue (total and 30d)
    total_rev = 0.0
    rev_30d = 0.0
    async for r in db.payment_transactions.aggregate([
        {"$match": {"status": "paid"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]):
        total_rev = float(r.get("total", 0))
    async for r in db.payment_transactions.aggregate([
        {"$match": {"status": "paid", "updated_at": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]):
        rev_30d = float(r.get("total", 0))

    # MRR = sum of monthly-subscription active licenses; annual ones contribute /12
    mrr = 0.0
    active_subs = 0
    async for lic in db.licenses.find({"status": "active", "stripe_subscription_id": {"$ne": None}}, {"_id": 0, "product_id": 1}):
        product = PRODUCTS.get(lic["product_id"])
        if not product or product["mode"] != "subscription":
            continue
        active_subs += 1
        if product["interval"] == "month":
            mrr += product["price"]
        elif product["interval"] == "year":
            mrr += product["price"] / 12

    total_affiliates = await db.affiliates.count_documents({})
    total_coupons = await db.coupons.count_documents({"active": True})

    # Unpaid affiliate commissions
    unpaid_commission = 0.0
    async for r in db.affiliate_sales.aggregate([
        {"$match": {"paid": False}},
        {"$group": {"_id": None, "total": {"$sum": "$commission"}}},
    ]):
        unpaid_commission = float(r.get("total", 0))

    return AdminStatsResponse(
        total_users=total_users,
        total_licenses_issued=total_licenses,
        active_licenses=active_licenses,
        expired_licenses=expired_licenses,
        revoked_licenses=revoked_licenses,
        total_revenue=round(total_rev, 2),
        revenue_last_30d=round(rev_30d, 2),
        mrr=round(mrr, 2),
        arr=round(mrr * 12, 2),
        active_subscriptions=active_subs,
        total_affiliates=total_affiliates,
        total_coupons=total_coupons,
        unpaid_affiliate_commission=round(unpaid_commission, 2),
    )


# ---------- user admin toggle ----------

@router.post("/users/{user_id}/admin")
async def promote_user(user_id: str, is_admin: bool, admin: dict = Depends(get_admin_user)):
    res = await db.users.update_one({"user_id": user_id}, {"$set": {"is_admin": is_admin}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user_id": user_id, "is_admin": is_admin}
