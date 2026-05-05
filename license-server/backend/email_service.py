"""SMTP email helper + HTML templates for the license server."""
from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Optional

import aiosmtplib

from config import (
    LICENSE_SERVER_DOMAIN,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)

logger = logging.getLogger("email")


def _is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


async def send_email(to_email: str, subject: str, html: str, text: Optional[str] = None) -> bool:
    """Send an email. Returns True on success, False on failure (never raises)."""
    if not _is_configured():
        logger.info(f"[email stub] would send '{subject}' to {to_email} (SMTP not configured)")
        return False
    if not to_email:
        return False

    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text or _strip_html(html))
    msg.add_alternative(html, subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER or None,
            password=SMTP_PASSWORD or None,
            start_tls=SMTP_PORT == 587,
            use_tls=SMTP_PORT == 465,
            timeout=15,
        )
        logger.info(f"Sent email: {subject} → {to_email}")
        return True
    except Exception as e:
        logger.error(f"SMTP send failed for {to_email}: {e}")
        return False


def _strip_html(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", "", html)
    return re.sub(r"\s+", " ", text).strip()


# ======================================================================
# Templates — plain f-strings so you can edit them without a template engine.
# ======================================================================

def _wrap(title: str, body_html: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f6fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:560px;margin:40px auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;">
    <div style="background:#0A0A0F;padding:20px 28px;">
      <div style="color:#fff;font-weight:800;font-size:20px;letter-spacing:-0.01em;">
        Stream<span style="color:#00E5FF;">Vault</span>
        <span style="font-size:10px;color:#A0A0AB;letter-spacing:0.15em;text-transform:uppercase;margin-left:8px;">License</span>
      </div>
    </div>
    <div style="padding:28px;color:#111;line-height:1.6;">
      <h1 style="font-size:22px;font-weight:800;margin:0 0 16px;color:#0A0A0F;">{title}</h1>
      {body_html}
    </div>
    <div style="background:#f9fafb;padding:16px 28px;color:#6b7280;font-size:12px;border-top:1px solid #e5e7eb;">
      Built by Qiary93 · <a href="https://{LICENSE_SERVER_DOMAIN.split('//')[-1]}" style="color:#00E5FF;text-decoration:none;">{LICENSE_SERVER_DOMAIN.split('//')[-1]}</a>
    </div>
  </div>
</body>
</html>
""".strip()


def tpl_license_issued(full_name: str, product_name: str, license_key: str, mode: str, renews_at: Optional[str]) -> tuple[str, str]:
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    renewal_line = (
        f"<p>Your subscription renews on <strong>{renews_at}</strong>. You can cancel anytime from your dashboard.</p>"
        if mode == "subscription" and renews_at else ""
    )
    body = f"""
<p>{greeting}</p>
<p>Your <strong>{product_name}</strong> license is ready. Copy this key and add it to your StreamVault <code>.env</code> on your VPS:</p>
<div style="background:#0A0A0F;color:#00E5FF;font-family:Menlo,monospace;padding:16px;border-radius:8px;margin:16px 0;text-align:center;font-size:16px;word-break:break-all;">
  {license_key}
</div>
<p><a href="{LICENSE_SERVER_DOMAIN}/dashboard" style="display:inline-block;background:#00E5FF;color:#000;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700;">Open your dashboard</a></p>
<p>Your license is ready to go. The first time your VPS pings our server, its IP is auto-bound.</p>
{renewal_line}
<p>Questions? Just reply to this email.</p>
"""
    subject = f"Your {product_name} license is ready"
    return subject, _wrap(subject, body)


def tpl_expiry_warning(full_name: str, product_name: str, days_left: int, renew_url: str) -> tuple[str, str]:
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    body = f"""
<p>{greeting}</p>
<p>Your <strong>{product_name}</strong> license expires in <strong>{days_left} day{'s' if days_left != 1 else ''}</strong>.</p>
<p>If your subscription doesn't renew automatically (e.g. your card failed), the auto-updater and premium features on your StreamVault install will lock.</p>
<p><a href="{renew_url}" style="display:inline-block;background:#00E5FF;color:#000;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700;">Manage subscription</a></p>
<p>You can check card on file, switch plans, or cancel from your dashboard.</p>
"""
    subject = f"Your {product_name} license expires in {days_left} day{'s' if days_left != 1 else ''}"
    return subject, _wrap(subject, body)


def tpl_license_revoked(full_name: str, product_name: str, reason: str) -> tuple[str, str]:
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    body = f"""
<p>{greeting}</p>
<p>Your <strong>{product_name}</strong> license has been revoked.</p>
<p><strong>Reason:</strong> {reason or 'No reason provided.'}</p>
<p>Premium features on your StreamVault install will stop working within 24 hours. Your streaming and chat keep running as normal.</p>
<p>If you believe this was in error, reply to this email and we'll investigate.</p>
"""
    subject = f"Your {product_name} license has been revoked"
    return subject, _wrap(subject, body)


def tpl_admin_sale(product_name: str, amount: float, customer_email: str, coupon: Optional[str] = None, affiliate: Optional[str] = None) -> tuple[str, str]:
    extras = []
    if coupon:
        extras.append(f"<li>Coupon: <code>{coupon}</code></li>")
    if affiliate:
        extras.append(f"<li>Affiliate: <code>{affiliate}</code></li>")
    extras_html = f"<ul>{''.join(extras)}</ul>" if extras else ""
    body = f"""
<p>💰 New sale:</p>
<ul>
  <li><strong>Product:</strong> {product_name}</li>
  <li><strong>Amount:</strong> ${amount:.2f}</li>
  <li><strong>Customer:</strong> {customer_email}</li>
</ul>
{extras_html}
<p><a href="{LICENSE_SERVER_DOMAIN}/admin" style="color:#00E5FF;">Open admin dashboard</a></p>
"""
    subject = f"💰 New sale: {product_name} (${amount:.2f})"
    return subject, _wrap(subject, body)
