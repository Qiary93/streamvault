"""Admin auto-updater routes.

Mounts under the main /api router. Endpoints:
    GET  /admin/updates/check     — git fetch + behind count + changelog
    POST /admin/updates/apply     — queue a host-side update job
    POST /admin/updates/rollback  — queue a rollback to a previous SHA
    GET  /admin/updates/status    — read the current job status
    GET  /admin/updates/history   — recent update jobs (audit log)

All routes require role==admin.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

import update_manager


def build_router(
    *,
    db: Any,
    get_current_user: Callable[..., Awaitable[dict]],
    send_email: Callable[[str, str, str, str], Awaitable[None]],
    logger,
) -> APIRouter:
    router = APIRouter()

    last_notified: Dict[str, Optional[str]] = {"started_at": None}

    async def _maybe_notify_update_outcome(status_payload: dict) -> None:
        """If the latest job just transitioned to success/error and we haven't
        sent a notification email for it yet, send one to the configured ADMIN_EMAIL."""
        if not isinstance(status_payload, dict):
            return
        s = status_payload.get("status")
        started = status_payload.get("started_at")
        if s not in ("success", "error") or not started:
            return
        if last_notified.get("started_at") == started:
            return  # already notified

        smtp_cfg = await db.admin_config.find_one({"type": "smtp"}, {"_id": 0})
        if not (smtp_cfg and smtp_cfg.get("enabled")):
            last_notified["started_at"] = started
            return

        admin_email = os.environ.get("ADMIN_EMAIL", "")
        if not admin_email:
            return

        site = os.environ.get("FRONTEND_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
        icon = "✅" if s == "success" else "⚠️"
        subject = f"{icon} StreamVault update {s}"
        body_html = f"""
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#111;background:#fff;padding:24px;border-radius:8px;">
  <h2 style="color:{'#10AC84' if s == 'success' else '#EE5A6F'};">{icon} Update {s}</h2>
  <p><strong>Stage:</strong> {status_payload.get('stage', '—')}</p>
  <p><strong>Message:</strong> {status_payload.get('message', '—')}</p>
  <p><strong>Started:</strong> {status_payload.get('started_at', '—')}<br/>
     <strong>Finished:</strong> {status_payload.get('finished_at', '—')}</p>
  <pre style="background:#f5f5f5;padding:12px;border-radius:4px;font-size:11px;white-space:pre-wrap;">{(status_payload.get('log_tail') or '')[-2000:]}</pre>
  <p style="margin-top:16px;"><a href="{site}/admin" style="background:#00E5FF;color:#000;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:700;">Open admin</a></p>
</div>
""".strip()
        body_text = f"Update {s}. Stage: {status_payload.get('stage', '—')}. {status_payload.get('message', '')}"
        try:
            await send_email(admin_email, subject, body_html, body_text)
            last_notified["started_at"] = started
            logger.info(f"Sent update-outcome email to {admin_email} for job {started}")
        except Exception as e:
            logger.error(f"Failed to send update notification: {e}")

    def _require_admin(user: dict) -> None:
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

    @router.get("/admin/updates/check")
    async def admin_check_updates(user: dict = Depends(get_current_user)):
        _require_admin(user)
        return await asyncio.get_event_loop().run_in_executor(None, update_manager.check_for_updates)

    @router.post("/admin/updates/apply")
    async def admin_apply_update(user: dict = Depends(get_current_user)):
        _require_admin(user)
        return await asyncio.get_event_loop().run_in_executor(None, update_manager.request_update)

    @router.post("/admin/updates/rollback")
    async def admin_rollback_update(request: Request, user: dict = Depends(get_current_user)):
        _require_admin(user)
        body = await request.json()
        target_sha = str(body.get("target_sha", "")).strip()
        return await asyncio.get_event_loop().run_in_executor(
            None, update_manager.request_rollback, target_sha
        )

    @router.get("/admin/updates/status")
    async def admin_update_status(user: dict = Depends(get_current_user)):
        _require_admin(user)
        payload = await asyncio.get_event_loop().run_in_executor(None, update_manager.get_status)
        # Best-effort email-on-completion (fire and forget).
        asyncio.create_task(_maybe_notify_update_outcome(payload))
        return payload

    @router.get("/admin/updates/history")
    async def admin_update_history(user: dict = Depends(get_current_user)):
        _require_admin(user)
        return await asyncio.get_event_loop().run_in_executor(None, update_manager.get_history)

    return router
