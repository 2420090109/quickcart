"""Payment service — Razorpay integration with proper idempotency.
The two paths that can mark a payment PAID:
  1. Client callback  → POST /orders/{code}/payment/verify
  2. Webhook          → POST /webhooks/razorpay
Both call the SAME idempotent handler. If both fire, we only apply the
change once. This is critical: Razorpay retries webhooks, and the client
may also fire after the webhook.
"""
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.razorpay import (
    RazorpayError,
    create_order as rzp_create_order,
    refund_payment as rzp_refund,
    verify_checkout_signature,
)
from app.models.enums import (
    NotificationChannel,
    NotificationStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
)
from app.models.notification import Notification
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.payment import Payment
from app.models.user import User
from app.schemas.payment import PaymentInitiateOut, PaymentOut
from app.services.order_service import _check_transition
logger = logging.getLogger(__name__)
def _rupees_to_paise(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))
async def _load_order_with_payments(
    db: AsyncSession, *, code: str
) -> Order:
    stmt = (
        select(Order)
        .where(Order.code == code)
        .options(
            selectinload(Order.payments),
            selectinload(Order.items),
            selectinload(Order.events),
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError(f"Order {code} not found.")
    return order
def _latest_payment(order: Order) -> Payment | None:
    if not order.payments:
        return None
    return sorted(order.payments, key=lambda p: p.created_at)[-1]
# =============================================================
# Initiate
# =============================================================
async def initiate_payment(
    db: AsyncSession, *, user: User, code: str
) -> PaymentInitiateOut:
    """Create a Razorpay order for an existing QuickCart order.
    Only valid when:
      - the order belongs to this user
      - the order is in PLACED status (not yet accepted)
      - the latest payment attempt is PENDING or FAILED (not PAID)
    """
    order = await _load_order_with_payments(db, code=code)
    if order.customer_id != user.id:
        raise NotFoundError(f"Order {code} not found.")
    if order.status not in (OrderStatus.PLACED, OrderStatus.ACCEPTED):
        raise ConflictError(
            f"Cannot initiate payment for order in status {order.status.value}."
        )
    payment = _latest_payment(order)
    if payment is None:
        raise ConflictError("No payment row exists for this order.")
    if payment.status == PaymentStatus.PAID:
        raise ConflictError("This order has already been paid.")
    if payment.method != PaymentMethod.RAZORPAY:
        raise ConflictError(
            f"Order was created with method {payment.method.value}. "
            "Only RAZORPAY orders support online payment."
        )
    # Create the Razorpay order
    try:
        rzp = await rzp_create_order(
            amount_paise=_rupees_to_paise(order.total),
            receipt=order.code,
            notes={"quickcart_order": order.code, "customer_id": str(user.id)},
        )
    except RazorpayError as e:
        raise ConflictError(f"Could not create Razorpay order: {e}") from e
    # Persist the Razorpay order id on our payment row
    payment.razorpay_order_id = rzp["id"]
    await db.commit()
    from app.core.config import settings
    return PaymentInitiateOut(
        razorpay_order_id=rzp["id"],
        razorpay_key_id=settings.RAZORPAY_KEY_ID,
        amount=rzp["amount"],
        currency=rzp.get("currency", "INR"),
        order_code=order.code,
        customer_name=user.full_name,
        customer_phone=user.phone,
        description=f"QuickCart order {order.code}",
    )
# =============================================================
# Client-side verification (after Checkout modal)
# =============================================================
async def verify_checkout_and_mark_paid(
    db: AsyncSession,
    *,
    user: User,
    code: str,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> PaymentOut:
    """Handle POST /orders/{code}/payment/verify."""
    order = await _load_order_with_payments(db, code=code)
    if order.customer_id != user.id:
        raise NotFoundError(f"Order {code} not found.")
    payment = _latest_payment(order)
    if payment is None:
        raise ConflictError("No payment row for this order.")
    # Idempotency: if already PAID, return quietly
    if payment.status == PaymentStatus.PAID:
        return PaymentOut.model_validate(payment)
    if payment.razorpay_order_id != razorpay_order_id:
        raise ValidationError("Razorpay order id does not match this order.")
    if not verify_checkout_signature(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        signature=razorpay_signature,
    ):
        raise ValidationError("Invalid payment signature.")
    await _mark_payment_paid(
        db,
        order=order,
        payment=payment,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
        source="client_verify",
    )
    await db.commit()
    await db.refresh(payment)
    return PaymentOut.model_validate(payment)
# =============================================================
# Server-side webhook
# =============================================================
async def handle_webhook_event(
    db: AsyncSession, *, event_type: str, payload: dict
) -> dict:
    """Called by the webhook route AFTER signature verification.
    Returns a small dict suitable as the HTTP response body.
    """
    if event_type == "payment.captured":
        return await _handle_captured(db, payload)
    if event_type == "payment.failed":
        return await _handle_failed(db, payload)
    # Anything else: accept and ignore
    logger.info("Ignoring webhook event_type=%s", event_type)
    return {"ok": True, "handled": False, "event_type": event_type}
async def _handle_captured(db: AsyncSession, payload: dict) -> dict:
    entity = (
        payload.get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )
    rzp_order_id = entity.get("order_id")
    rzp_payment_id = entity.get("id")
    if not rzp_order_id or not rzp_payment_id:
        return {"ok": False, "reason": "missing order_id or payment id"}
    payment = (
        await db.execute(
            select(Payment)
            .where(Payment.razorpay_order_id == rzp_order_id)
            .options(selectinload(Payment.order))
        )
    ).scalar_one_or_none()
    if payment is None:
        logger.warning("Webhook captured for unknown rzp_order_id=%s", rzp_order_id)
        return {"ok": True, "handled": False, "reason": "unknown order"}
    # Idempotency
    if payment.status == PaymentStatus.PAID:
        return {"ok": True, "handled": False, "reason": "already paid"}
    await _mark_payment_paid(
        db,
        order=payment.order,
        payment=payment,
        razorpay_payment_id=rzp_payment_id,
        razorpay_signature=entity.get("signature"),
        source="webhook",
    )
    await db.commit()
    return {"ok": True, "handled": True, "source": "webhook"}
async def _handle_failed(db: AsyncSession, payload: dict) -> dict:
    entity = (
        payload.get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )
    rzp_order_id = entity.get("order_id")
    reason = entity.get("error_description") or "Payment failed"
    if not rzp_order_id:
        return {"ok": False, "reason": "missing order_id"}
    payment = (
        await db.execute(
            select(Payment).where(Payment.razorpay_order_id == rzp_order_id)
        )
    ).scalar_one_or_none()
    if payment is None:
        return {"ok": True, "handled": False, "reason": "unknown order"}
    if payment.status == PaymentStatus.PAID:
        return {"ok": True, "handled": False, "reason": "already paid"}
    payment.status = PaymentStatus.FAILED
    payment.failure_reason = reason
    await db.commit()
    return {"ok": True, "handled": True}
# =============================================================
# Shared: mark payment paid (idempotent core)
# =============================================================
async def _mark_payment_paid(
    db: AsyncSession,
    *,
    order: Order,
    payment: Payment,
    razorpay_payment_id: str,
    razorpay_signature: str | None,
    source: str,
) -> None:
    """Single place that flips a payment to PAID.
    Also moves the order from PLACED → ACCEPTED, since a paid order is
    ready for the shop to work on.
    """
    now = datetime.now(timezone.utc)
    payment.status = PaymentStatus.PAID
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.paid_at = now
    # Move order forward if it's still PLACED
    if order.status == OrderStatus.PLACED:
        try:
            _check_transition(order.status, OrderStatus.ACCEPTED)
        except Exception:
            # Shouldn't happen, but be defensive
            pass
        else:
            previous = order.status
            order.status = OrderStatus.ACCEPTED
            order.accepted_at = now
            db.add(
                OrderEvent(
                    order_id=order.id,
                    actor_id=None,
                    actor_role="system",
                    from_status=previous,
                    to_status=OrderStatus.ACCEPTED,
                    note=f"Auto-accepted after payment ({source}).",
                )
            )
            db.add(
                Notification(
                    user_id=order.customer_id,
                    channel=NotificationChannel.IN_APP,
                    status=NotificationStatus.QUEUED,
                    event_type="order.accepted",
                    title="Payment received",
                    body=(
                        f"Payment for order {order.code} was successful. "
                        "The shop will start preparing your order."
                    ),
                )
            )
    db.add(
        Notification(
            user_id=order.customer_id,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            event_type="payment.captured",
            title="Payment successful",
            body=f"We received ₹{payment.amount} for order {order.code}.",
        )
    )
# =============================================================
# Refund (called on cancel of a PAID order)
# =============================================================
async def refund_for_order(
    db: AsyncSession, *, order: Order, reason: str
) -> None:
    """Refund the paid amount for an order (idempotent)."""
    payment = _latest_payment(order)
    if payment is None or payment.status != PaymentStatus.PAID:
        return
    if not payment.razorpay_payment_id:
        logger.warning("Cannot refund order %s — no razorpay_payment_id", order.code)
        return
    try:
        resp = await rzp_refund(
            payment_id=payment.razorpay_payment_id,
            amount_paise=_rupees_to_paise(payment.amount),
            notes={"reason": reason[:100], "order_code": order.code},
        )
    except RazorpayError as e:
        logger.error("Refund failed for %s: %s", order.code, e)
        return
    payment.status = PaymentStatus.REFUNDED
    payment.refunded_at = datetime.now(timezone.utc)
    payment.refund_amount = payment.amount
    # Store the refund id for audit
    payment.raw_webhook_payload = (payment.raw_webhook_payload or "") + f"\nrefund:{resp.get('id')}"
    db.add(
        Notification(
            user_id=order.customer_id,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            event_type="payment.refunded",
            title="Refund processed",
            body=f"A refund of ₹{payment.amount} for order {order.code} is on the way.",
        )
    )