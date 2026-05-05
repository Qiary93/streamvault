"""Coupon management + validation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_admin_user, get_current_user
from config import COUPON_MAX_DISCOUNT_PERCENT, PRODUCTS
from db import db
from models import (
    CouponCreateRequest,
    CouponResponse,
    CouponUpdateRequest,
    CouponValidateRequest,
    CouponValidateResponse,
)

router = APIRouter(prefix="/api/coupons", tags=["coupons"])


def _serialize(doc: dict) -> CouponResponse:
    return CouponResponse(
        code=doc["code"],
        description=doc.get("description"),
        discount_type=doc["discount_type"],
        discount_value=doc["discount_value"],
        max_uses=doc.get("max_uses", 0),
        used_count=doc.get("used_count", 0),
        expires_at=doc.get("expires_at"),
        product_ids=doc.get("product_ids", []),
        active=doc.get("active", True),
        created_at=doc["created_at"],
    )


def _is_expired(doc: dict) -> bool:
    exp = doc.get("expires_at")
    if not exp:
        return False
    if isinstance(exp, datetime) and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < datetime.now(timezone.utc)


def _compute_discount(coupon: dict, base_price: float) -> float:
    """Returns the final price after applying the coupon. Never below $0.50."""
    if coupon["discount_type"] == "percentage":
        discount = base_price * (coupon["discount_value"] / 100.0)
    else:  # fixed
        discount = float(coupon["discount_value"])
    final = max(0.50, base_price - discount)
    return round(final, 2)


async def apply_coupon_to_price(code: Optional[str], product_id: str, base_price: float) -> tuple[float, Optional[dict]]:
    """Used by checkout.py. Returns (final_price, coupon_doc_or_None)."""
    if not code:
        return base_price, None
    code = code.strip().upper()
    doc = await db.coupons.find_one({"code": code}, {"_id": 0})
    if not doc or not doc.get("active"):
        return base_price, None
    if _is_expired(doc):
        return base_price, None
    if doc.get("max_uses", 0) > 0 and doc.get("used_count", 0) >= doc["max_uses"]:
        return base_price, None
    if doc.get("product_ids") and product_id not in doc["product_ids"]:
        return base_price, None
    return _compute_discount(doc, base_price), doc


# ---------- public endpoint ----------

@router.post("/validate", response_model=CouponValidateResponse)
async def validate_coupon(body: CouponValidateRequest):
    product = PRODUCTS.get(body.product_id)
    if not product:
        return CouponValidateResponse(valid=False, message="Unknown product")
    final, doc = await apply_coupon_to_price(body.code, body.product_id, product["price"])
    if not doc:
        return CouponValidateResponse(valid=False, message="Coupon is invalid, expired, or doesn't apply to this product.")
    return CouponValidateResponse(
        valid=True,
        discount_type=doc["discount_type"],
        discount_value=doc["discount_value"],
        final_price=final,
        message="Coupon applied",
    )


# ---------- admin endpoints ----------

@router.get("", response_model=List[CouponResponse])
async def list_coupons(admin: dict = Depends(get_admin_user)):
    cur = db.coupons.find({}, {"_id": 0}).sort("created_at", -1)
    return [_serialize(d) async for d in cur]


@router.post("", response_model=CouponResponse, status_code=201)
async def create_coupon(body: CouponCreateRequest, admin: dict = Depends(get_admin_user)):
    if body.discount_type not in ("percentage", "fixed"):
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'fixed'")
    if body.discount_type == "percentage" and body.discount_value > COUPON_MAX_DISCOUNT_PERCENT:
        raise HTTPException(status_code=400, detail=f"Percentage can't exceed {COUPON_MAX_DISCOUNT_PERCENT}%")

    code = body.code.strip().upper()
    if await db.coupons.find_one({"code": code}):
        raise HTTPException(status_code=409, detail="Coupon code already exists")

    doc = {
        "code": code,
        "description": body.description,
        "discount_type": body.discount_type,
        "discount_value": body.discount_value,
        "max_uses": body.max_uses,
        "used_count": 0,
        "expires_at": body.expires_at,
        "product_ids": body.product_ids,
        "active": body.active,
        "created_at": datetime.now(timezone.utc),
        "created_by": admin["user_id"],
    }
    await db.coupons.insert_one(doc)
    return _serialize(doc)


@router.put("/{code}", response_model=CouponResponse)
async def update_coupon(code: str, body: CouponUpdateRequest, admin: dict = Depends(get_admin_user)):
    code = code.strip().upper()
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = await db.coupons.update_one({"code": code}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Coupon not found")
    doc = await db.coupons.find_one({"code": code}, {"_id": 0})
    return _serialize(doc)


@router.delete("/{code}", status_code=204)
async def delete_coupon(code: str, admin: dict = Depends(get_admin_user)):
    code = code.strip().upper()
    await db.coupons.delete_one({"code": code})
    return None


async def increment_coupon_usage(code: str) -> None:
    """Called from the webhook on successful payment."""
    if not code:
        return
    await db.coupons.update_one({"code": code.upper()}, {"$inc": {"used_count": 1}})
