"""
stripe_shim.py — drop-in replacement for `emergentintegrations.payments.stripe.checkout`.

Implements the same API surface (`StripeCheckout`, `CheckoutSessionRequest`,
`CheckoutSessionResponse`, `CheckoutStatusResponse`) using the standard
`stripe` SDK, so the app runs on any host without requiring Emergent's
private package registry.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import stripe as stripe_sdk


@dataclass
class CheckoutSessionRequest:
    amount: float
    currency: str = "usd"
    success_url: str = ""
    cancel_url: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckoutSessionResponse:
    url: str
    session_id: str


@dataclass
class CheckoutStatusResponse:
    session_id: str
    payment_status: str  # "paid" | "unpaid" | ...
    status: str
    amount_total: Optional[int] = None
    currency: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebhookResponse:
    session_id: str
    payment_status: str
    event_type: str


class StripeCheckout:
    """
    Async-compatible minimal Stripe Checkout client.
    All methods are coroutines to match the emergentintegrations signature,
    but the underlying `stripe` SDK calls are synchronous (they're fast).
    """

    def __init__(self, api_key: str, webhook_url: str = ""):
        if not api_key:
            raise ValueError("STRIPE_API_KEY is required")
        self._api_key = api_key
        self._webhook_url = webhook_url
        # stripe_sdk maintains api_key at module level; set it each call to be
        # safe in case another integration overrides it.
        stripe_sdk.api_key = api_key

    async def create_checkout_session(
        self, request: CheckoutSessionRequest
    ) -> CheckoutSessionResponse:
        stripe_sdk.api_key = self._api_key
        amount_cents = int(round(float(request.amount) * 100))
        session = stripe_sdk.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": request.currency,
                        "product_data": {"name": "StreamVault payment"},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata=request.metadata or {},
        )
        return CheckoutSessionResponse(url=session.url, session_id=session.id)

    async def get_checkout_status(self, session_id: str) -> CheckoutStatusResponse:
        stripe_sdk.api_key = self._api_key
        session = stripe_sdk.checkout.Session.retrieve(session_id)
        return CheckoutStatusResponse(
            session_id=session.id,
            payment_status=session.payment_status or "unpaid",
            status=session.status or "open",
            amount_total=session.amount_total,
            currency=session.currency,
            metadata=dict(session.metadata or {}),
        )

    async def handle_webhook(self, body: bytes, signature: str) -> WebhookResponse:
        stripe_sdk.api_key = self._api_key
        secret = (
            # Prefer a dedicated checkout webhook secret if set, otherwise
            # fall back to the Connect webhook secret (same Stripe endpoint
            # can handle both payment_intent and checkout events).
            __import__("os").environ.get("STRIPE_WEBHOOK_SECRET")
            or __import__("os").environ.get("STRIPE_CONNECT_WEBHOOK_SECRET", "")
        )
        if not secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET not configured")
        event = stripe_sdk.Webhook.construct_event(body, signature, secret)

        session_id = ""
        payment_status = "unknown"
        data_obj = (event.get("data") or {}).get("object") or {}
        if event.get("type", "").startswith("checkout.session."):
            session_id = data_obj.get("id", "")
            payment_status = data_obj.get("payment_status", "unknown")
        return WebhookResponse(
            session_id=session_id,
            payment_status=payment_status,
            event_type=event.get("type", ""),
        )
