"""Customer-facing license routes — list, view, change IP."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from config import IP_CHANGE_LIMIT_PER_MONTH, IP_CHANGE_WINDOW_DAYS, PRODUCTS
from db import db
from models import ChangeIpRequest, LicenseResponse

router = APIRouter(prefix="/api/licenses", tags=["licenses"])

# Accepts IPv4 or IPv6 (loose check — strict validation isn't worth the noise here).
_IP_RE = re.compile(r"^[0-9a-fA-F:.]{7,45}$")


async def _ip_changes_used(license_id: str) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=IP_CHANGE_WINDOW_DAYS)
    return await db.ip_change_log.count_documents({
        "license_id": license_id,
        "changed_at": {"$gte": cutoff},
    })


def _serialize_license(lic: dict, ip_changes_used: int) -> LicenseResponse:
    product = PRODUCTS.get(lic["product_id"], {})
    bound_ips = lic.get("bound_ips", [])
    return LicenseResponse(
        license_id=lic["license_id"],
        license_key=lic["license_key"],
        product_id=lic["product_id"],
        product_name=product.get("name", lic["product_id"]),
        status=lic["status"],
        bound_ip=bound_ips[0] if bound_ips else None,
        bound_ips=bound_ips,
        max_ips=lic.get("max_ips", 1),
        expires_at=lic.get("expires_at"),
        created_at=lic["created_at"],
        ip_changes_remaining=max(0, IP_CHANGE_LIMIT_PER_MONTH - ip_changes_used),
    )


@router.get("", response_model=List[LicenseResponse])
async def list_my_licenses(user: dict = Depends(get_current_user)):
    cursor = db.licenses.find(
        {"user_id": user["user_id"]},
        {"_id": 0},
    ).sort("created_at", -1)
    out: List[LicenseResponse] = []
    async for lic in cursor:
        used = await _ip_changes_used(lic["license_id"])
        out.append(_serialize_license(lic, used))
    return out


@router.post("/change-ip", response_model=LicenseResponse)
async def change_ip(body: ChangeIpRequest, user: dict = Depends(get_current_user)):
    if not _IP_RE.match(body.new_ip):
        raise HTTPException(status_code=400, detail="Invalid IP address")

    lic = await db.licenses.find_one(
        {"license_id": body.license_id, "user_id": user["user_id"]}, {"_id": 0},
    )
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    if lic["status"] != "active":
        raise HTTPException(status_code=400, detail=f"License is {lic['status']}, can't change IP")

    used = await _ip_changes_used(body.license_id)
    if used >= IP_CHANGE_LIMIT_PER_MONTH:
        raise HTTPException(
            status_code=429,
            detail=f"IP change limit reached ({IP_CHANGE_LIMIT_PER_MONTH} per {IP_CHANGE_WINDOW_DAYS} days). Try again later or contact support.",
        )

    bound_ips = lic.get("bound_ips", [])
    max_ips = lic.get("max_ips", 1)
    old_ips = list(bound_ips)

    if body.new_ip in bound_ips:
        # Already bound — no-op, but don't penalize their change quota.
        return _serialize_license(lic, used)

    if max_ips == 1:
        # Replace the single bound IP.
        bound_ips = [body.new_ip]
    else:
        # Multi-IP license — append, evict the oldest if full.
        bound_ips.append(body.new_ip)
        if len(bound_ips) > max_ips:
            bound_ips = bound_ips[-max_ips:]

    await db.licenses.update_one(
        {"license_id": body.license_id},
        {"$set": {"bound_ips": bound_ips, "updated_at": datetime.now(timezone.utc)}},
    )
    await db.ip_change_log.insert_one({
        "license_id": body.license_id,
        "user_id": user["user_id"],
        "old_ips": old_ips,
        "new_ips": bound_ips,
        "changed_at": datetime.now(timezone.utc),
    })

    fresh = await db.licenses.find_one({"license_id": body.license_id}, {"_id": 0})
    return _serialize_license(fresh, used + 1)
