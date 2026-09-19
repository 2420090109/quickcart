"""Minimal async Razorpay REST client.
We don't pull in the official SDK — it's synchronous and doesn't play
nicely with FastAPI's async model. Instead we call the REST API directly
with httpx. This is also more explicit and easier to debug.
Razorpay API docs: https://razorpay.com/docs/api/
"""
import base64
import hashlib
import hmac
import logging
from typing import Any
import httpx
from app.core.config import settings
logger = logging.getLogger(__name__)
BASE_URL = "https://api.razorpay.com/v1"
class RazorpayError(Exception):
    """Raised when Razorpay returns a non-2xx response."""
def _auth_header() -> dict[str, str]:
    """Basic auth: base64(key_id:key_secret)."""
    token = f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}"
    b64 = base64.b64encode(token.encode()).decode()
    return {"Authorization": f"Basic {b64}"}
async def create_order(
    *,
    amount_paise: int,
    receipt: str,
    notes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a Razorpay order.
    amount_paise: amount in paise (smallest currency unit). ₹100 = 10000.
    receipt: our internal order code, shown in the Razorpay dashboard.
    """
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": notes or {},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{BASE_URL}/orders",
            json=payload,
            headers={**_auth_header(), "Content-Type": "application/json"},
        )
    if resp.status_code >= 400:
        logger.error("Razorpay create_order failed: %s %s", resp.status_code, resp.text)
        raise RazorpayError(
            f"Razorpay returned {resp.status_code}: {resp.text[:200]}"
        )
    return resp.json()
async def fetch_payment(payment_id: str) -> dict[str, Any]:
    """Fetch a payment by its razorpay_payment_id."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{BASE_URL}/payments/{payment_id}",
            headers=_auth_header(),
        )
    if resp.status_code >= 400:
        raise RazorpayError(
            f"Razorpay fetch_payment {payment_id} failed: {resp.status_code}"
        )
    return resp.json()
async def refund_payment(
    *, payment_id: str, amount_paise: int | None = None, notes: dict[str, str] | None = None
) -> dict[str, Any]:
    """Refund a captured payment, fully or partially."""
    payload: dict[str, Any] = {"notes": notes or {}}
    if amount_paise is not None:
        payload["amount"] = amount_paise
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{BASE_URL}/payments/{payment_id}/refund",
            json=payload,
            headers={**_auth_header(), "Content-Type": "application/json"},
        )
    if resp.status_code >= 400:
        raise RazorpayError(f"Refund failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()
# =============================================================
# Signature verification
# =============================================================
def verify_checkout_signature(
    *, razorpay_order_id: str, razorpay_payment_id: str, signature: str
) -> bool:
    """Verify the signature returned by Razorpay Checkout (client-side).
    Signed string: "<order_id>|<payment_id>"
    Secret: RAZORPAY_KEY_SECRET
    """
    body = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
def verify_webhook_signature(*, raw_body: bytes, signature: str) -> bool:
    """Verify the X-Razorpay-Signature header on webhooks.
    Signed data: the raw request body (bytes, unmodified)
    Secret: RAZORPAY_WEBHOOK_SECRET
    """
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        logger.warning("RAZORPAY_WEBHOOK_SECRET is empty — webhooks will fail.")
        return False
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)