"""Affiliate program — users become affiliates, earn commissions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_admin_user, get_current_user
from config import AFFILIATE_DEFAULT_COMMISSION_PERCENT, AFFILIATE_MIN_PAYOUT_USD
from db import db
from models import AffiliateResponse, AffiliateSaleResponse, AffiliateSignupRequest

router = APIRouter(prefix="/api/affiliates", tags=["affiliates"])


def _serialize(aff: dict) -> AffiliateResponse:
    total_revenue = aff.get("total_revenue", 0.0)
    total_commission = aff.get("total_commission", 0.0)
    paid_out = aff.get("paid_out", 0.0)
    return AffiliateResponse(
        user_id=aff["user_id"],
        code=aff["code"],
        commission_percent=aff.get("commission_percent", AFFILIATE_DEFAULT_COMMISSION_PERCENT),
        total_sales=aff.get("total_sales", 0),
        total_revenue=round(total_revenue, 2),
        total_commission=round(total_commission, 2),
        paid_out=round(paid_out, 2),
        balance_owed=round(total_commission - paid_out, 2),
        created_at=aff["created_at"],
    )


async def get_affiliate_by_code(code: Optional[str]) -> Optional[dict]:
    if not code:
        return None
    return await db.affiliates.find_one({"code": code.strip().upper()}, {"_id": 0})


async def record_affiliate_sale(
    affiliate_code: Optional[str],
    buyer_user_id: str,
    license_id: str,
    product_id: str,
    amount: float,
) -> None:
    """Called from the webhook on paid checkouts."""
    aff = await get_affiliate_by_code(affiliate_code)
    if not aff:
        return
    if aff["user_id"] == buyer_user_id:
        return   # affiliates can't earn from their own purchases
    commission = round(amount * aff["commission_percent"] / 100.0, 2)
    await db.affiliate_sales.insert_one({
        "sale_id": f"sale_{uuid.uuid4().hex[:12]}",
        "affiliate_id": aff["user_id"],
        "affiliate_code": aff["code"],
        "buyer_user_id": buyer_user_id,
        "license_id": license_id,
        "product_id": product_id,
        "amount": amount,
        "commission": commission,
        "paid": False,
        "created_at": datetime.now(timezone.utc),
    })
    await db.affiliates.update_one(
        {"user_id": aff["user_id"]},
        {"$inc": {
            "total_sales": 1,
            "total_revenue": amount,
            "total_commission": commission,
        }},
    )


# ---------- self-service ----------

@router.get("/me", response_model=Optional[AffiliateResponse])
async def get_my_affiliate(user: dict = Depends(get_current_user)):
    aff = await db.affiliates.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return _serialize(aff) if aff else None


@router.post("/signup", response_model=AffiliateResponse, status_code=201)
async def affiliate_signup(body: AffiliateSignupRequest, user: dict = Depends(get_current_user)):
    """Turn the logged-in user into an affiliate with a custom referral code."""
    if await db.affiliates.find_one({"user_id": user["user_id"]}):
        raise HTTPException(status_code=409, detail="You already have an affiliate account")
    code = body.code.strip().upper()
    if await db.affiliates.find_one({"code": code}):
        raise HTTPException(status_code=409, detail="That code is already taken — pick another")

    doc = {
        "user_id": user["user_id"],
        "user_email": user["email"],
        "code": code,
        "commission_percent": AFFILIATE_DEFAULT_COMMISSION_PERCENT,
        "total_sales": 0,
        "total_revenue": 0.0,
        "total_commission": 0.0,
        "paid_out": 0.0,
        "created_at": datetime.now(timezone.utc),
    }
    await db.affiliates.insert_one(doc)
    return _serialize(doc)


@router.get("/me/sales", response_model=List[AffiliateSaleResponse])
async def my_sales(user: dict = Depends(get_current_user), limit: int = 50):
    aff = await db.affiliates.find_one({"user_id": user["user_id"]}, {"_id": 0, "user_id": 1})
    if not aff:
        return []
    cur = db.affiliate_sales.find({"affiliate_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).limit(limit)
    out = []
    async for sale in cur:
        buyer = await db.users.find_one({"user_id": sale["buyer_user_id"]}, {"_id": 0, "email": 1})
        out.append(AffiliateSaleResponse(
            sale_id=sale["sale_id"],
            buyer_email=_mask_email(buyer["email"] if buyer else "unknown"),
            product_id=sale["product_id"],
            amount=sale["amount"],
            commission=sale["commission"],
            paid=sale.get("paid", False),
            created_at=sale["created_at"],
        ))
    return out


def _mask_email(email: str) -> str:
    try:
        user, domain = email.split("@")
        if len(user) <= 2:
            return f"{user[0]}***@{domain}"
        return f"{user[0]}{'*' * (len(user) - 2)}{user[-1]}@{domain}"
    except ValueError:
        return "***"


# ---------- admin-only ----------

@router.get("", response_model=List[AffiliateResponse])
async def list_affiliates(admin: dict = Depends(get_admin_user)):
    cur = db.affiliates.find({}, {"_id": 0}).sort("total_commission", -1)
    return [_serialize(d) async for d in cur]


@router.post("/{user_id}/mark-paid")
async def mark_commissions_paid(user_id: str, admin: dict = Depends(get_admin_user)):
    """Mark all unpaid sales for this affiliate as paid, credit their paid_out total."""
    aff = await db.affiliates.find_one({"user_id": user_id}, {"_id": 0})
    if not aff:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    unpaid_cur = db.affiliate_sales.find({"affiliate_id": user_id, "paid": False}, {"_id": 0, "commission": 1})
    total_to_pay = 0.0
    count = 0
    async for s in unpaid_cur:
        total_to_pay += float(s.get("commission", 0))
        count += 1
    total_to_pay = round(total_to_pay, 2)
    await db.affiliate_sales.update_many(
        {"affiliate_id": user_id, "paid": False},
        {"$set": {"paid": True, "paid_at": datetime.now(timezone.utc)}},
    )
    await db.affiliates.update_one(
        {"user_id": user_id},
        {"$inc": {"paid_out": total_to_pay}},
    )
    return {"sales_marked_paid": count, "total_amount": total_to_pay, "min_payout": AFFILIATE_MIN_PAYOUT_USD}


@router.put("/{user_id}/commission")
async def update_commission(user_id: str, commission_percent: float, admin: dict = Depends(get_admin_user)):
    if commission_percent < 0 or commission_percent > 100:
        raise HTTPException(status_code=400, detail="commission_percent must be between 0 and 100")
    res = await db.affiliates.update_one(
        {"user_id": user_id},
        {"$set": {"commission_percent": commission_percent}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    return {"ok": True, "commission_percent": commission_percent}
