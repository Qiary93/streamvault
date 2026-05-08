"""
license_manager.py — buyer-side license validation for StreamVault.

Pings the DramaroSub license server every 24 hours to confirm this install's
license is still active and the bound IP matches.

Configuration in `/app/backend/.env`:
    STREAMVAULT_LICENSE_KEY=DSB-XXXXX-XXXXX-XXXXX-XXXXX
    LICENSE_SERVER_URL=https://license.stream-vault.eu

Behavior:
- On startup: validates once. If invalid, sets status accordingly (does NOT crash).
- Every 24h thereafter: re-validates in a background task.
- Caches the last successful validation timestamp. If the license server is
  unreachable (network blip, planned maintenance), we keep trusting the last
  successful response for up to OFFLINE_GRACE_DAYS (default 14).
- Status is exposed via `get_license_status()` for the admin panel.

Soft enforcement: We never break streaming. Pricing-tier-locked features (like
the in-app auto-updater) check `is_license_valid()` and gate themselves.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import httpx
except ImportError:        # httpx is optional — fall back to "license check disabled"
    httpx = None  # type: ignore

logger = logging.getLogger("license")

LICENSE_SERVER_URL = os.environ.get("LICENSE_SERVER_URL", "https://license.stream-vault.eu")
LICENSE_KEY = os.environ.get("STREAMVAULT_LICENSE_KEY", "").strip()
# Set ENFORCE_LICENSE=false in the env to disable hard enforcement (development).
ENFORCE_LICENSE = os.environ.get("ENFORCE_LICENSE", "true").strip().lower() not in ("0", "false", "no", "off")
VALIDATION_INTERVAL_HOURS = 24
OFFLINE_GRACE_DAYS = 14
HTTP_TIMEOUT = 10.0


# In-process cache.
_state: dict = {
    "valid": False,
    "status": "unchecked",     # active | expired | revoked | ip_mismatch | not_found | unconfigured | server_unreachable | unchecked
    "product_id": None,
    "product_name": None,
    "expires_at": None,
    "message": "License has not been validated yet.",
    "last_check_at": None,
    "last_success_at": None,
}
_loop_task: Optional[asyncio.Task] = None


def _detect_public_ip() -> str:
    """Best-effort guess of the host's public IP. Empty string if we can't tell —
    in which case the license server will fall back to the request's source IP.
    """
    # The license server checks the X-Forwarded-For header automatically, so we
    # don't strictly need to send our own IP. We do try, however, so that
    # validation works even when behind unusual NAT setups.
    for env_key in ("PUBLIC_IP", "HOST_IP", "SERVER_IP"):
        v = os.environ.get(env_key)
        if v:
            return v.strip()
    try:
        # 1.1.1.1 will never accept the connection, but the OS will pick the
        # outbound interface IP for the route — which is what we want.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("1.1.1.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


async def validate_now() -> dict:
    """Hit the license server once and update _state. Always returns _state."""
    now = datetime.now(timezone.utc)
    _state["last_check_at"] = now

    if not LICENSE_KEY:
        _state.update({
            "valid": False,
            "status": "unconfigured",
            "message": "STREAMVAULT_LICENSE_KEY is not set in the environment.",
        })
        return dict(_state)

    if httpx is None:
        _state.update({
            "valid": False,
            "status": "unconfigured",
            "message": "httpx not installed — can't reach the license server.",
        })
        return dict(_state)

    server_ip = _detect_public_ip()
    payload = {"license_key": LICENSE_KEY, "server_ip": server_ip}
    url = f"{LICENSE_SERVER_URL.rstrip('/')}/api/license/validate"

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
    except Exception as e:
        logger.warning(f"License server unreachable: {e}")
        # If we have a recent successful validation, keep trusting it.
        last_ok = _state.get("last_success_at")
        if last_ok and (now - last_ok) < timedelta(days=OFFLINE_GRACE_DAYS):
            _state.update({
                "valid": True,
                "status": "active",
                "message": f"License server unreachable; trusting cached validation (last OK {last_ok.isoformat()}).",
            })
        else:
            _state.update({
                "valid": False,
                "status": "server_unreachable",
                "message": f"License server unreachable for >{OFFLINE_GRACE_DAYS} days. Premium features locked.",
            })
        return dict(_state)

    valid = bool(data.get("valid"))
    _state.update({
        "valid": valid,
        "status": data.get("status", "unknown"),
        "product_id": data.get("product_id"),
        "product_name": data.get("product_name"),
        "expires_at": data.get("expires_at"),
        "message": data.get("message", ""),
    })
    if valid:
        _state["last_success_at"] = now
        logger.info(f"License OK ({_state['product_name']})")
    else:
        logger.warning(f"License check failed: {_state['status']} — {_state['message']}")
    return dict(_state)


async def _periodic_loop() -> None:
    interval = VALIDATION_INTERVAL_HOURS * 3600
    while True:
        try:
            await validate_now()
        except Exception as e:
            logger.exception(f"License validation loop error: {e}")
        await asyncio.sleep(interval)


def get_license_status() -> dict:
    """Read-only snapshot for the admin panel."""
    return dict(_state)


def is_license_valid() -> bool:
    return bool(_state.get("valid"))


def is_enforced() -> bool:
    """Returns True if hard enforcement is active in this install."""
    return ENFORCE_LICENSE


async def start_background_validator() -> None:
    """Call this from your FastAPI startup hook."""
    global _loop_task
    if _loop_task is not None:
        return
    # First validation runs synchronously so admin sees status on first paint.
    await validate_now()
    _loop_task = asyncio.create_task(_periodic_loop())
