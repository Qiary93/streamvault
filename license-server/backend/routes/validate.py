"""License validation endpoint — called by buyer's StreamVault installs every 24h.

Public endpoint (no JWT). Authentication is the license_key itself + IP match.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from config import PRODUCTS
from db import db
from models import ValidateRequest, ValidateResponse

logger = logging.getLogger("validate")

router = APIRouter(prefix="/api/license", tags=["validate"])


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/validate", response_model=ValidateResponse)
async def validate_license(body: ValidateRequest, request: Request):
    lic = await db.licenses.find_one({"license_key": body.license_key.strip()}, {"_id": 0})
    if not lic:
        return ValidateResponse(valid=False, status="not_found", message="License key not recognized.")

    if lic["status"] != "active":
        return ValidateResponse(
            valid=False,
            status=lic["status"],
            product_id=lic.get("product_id"),
            product_name=PRODUCTS.get(lic.get("product_id", ""), {}).get("name"),
            message=f"License is {lic['status']}.",
        )

    expires = lic.get("expires_at")
    if expires and isinstance(expires, datetime):
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            await db.licenses.update_one(
                {"license_id": lic["license_id"]},
                {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc)}},
            )
            return ValidateResponse(
                valid=False,
                status="expired",
                product_id=lic.get("product_id"),
                expires_at=expires,
                message="License has expired. Please renew your subscription.",
            )

    bound_ips = lic.get("bound_ips", [])
    sender_ip = body.server_ip or _client_ip(request)

    # First-ever validation: auto-bind the IP (saves the customer a manual step).
    if not bound_ips:
        await db.licenses.update_one(
            {"license_id": lic["license_id"]},
            {"$set": {"bound_ips": [sender_ip], "updated_at": datetime.now(timezone.utc)}},
        )
        bound_ips = [sender_ip]

    if sender_ip not in bound_ips:
        return ValidateResponse(
            valid=False,
            status="ip_mismatch",
            product_id=lic.get("product_id"),
            product_name=PRODUCTS.get(lic.get("product_id", ""), {}).get("name"),
            message=f"Server IP {sender_ip} is not authorized for this license. Update your bound IP in your dashboard.",
        )

    # Record the successful check (light-touch audit trail).
    await db.licenses.update_one(
        {"license_id": lic["license_id"]},
        {"$set": {"last_validated_at": datetime.now(timezone.utc), "last_validated_ip": sender_ip}},
    )

    return ValidateResponse(
        valid=True,
        status="active",
        product_id=lic.get("product_id"),
        product_name=PRODUCTS.get(lic.get("product_id", ""), {}).get("name"),
        expires_at=lic.get("expires_at"),
        message="OK",
    )
