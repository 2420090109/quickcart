"""Order service â€” checkout, state machine, and history."""
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.address import Address
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.enums import (
    NotificationChannel,
    NotificationStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    SlotType,
    UserRole,
)
from app.models.inventory import Inventory
from app.models.notification import Notification
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.shop import Shop
from app.models.user import User
from app.schemas.order import OrderSummaryOut
# =============================================================
# State machine
# =============================================================
LEGAL_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PLACED: {
        OrderStatus.ACCEPTED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.ACCEPTED: {
        OrderStatus.PACKING,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PACKING: {
        OrderStatus.PACKED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PACKED: {
        OrderStatus.OUT_FOR_DELIVERY,
        OrderStatus.CANCELLED,
    },
    OrderStatus.OUT_FOR_DELIVERY: {
        OrderStatus.DELIVERED,
    },
    OrderStatus.DELIVERED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.CANCELLED: {OrderStatus.REFUNDED},
    OrderStatus.REFUNDED: set(),
}
def _check_transition(from_status: OrderStatus, to_status: OrderStatus) -> None:
    allowed = LEGAL_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise ConflictError(
            f"Cannot move order from {from_status.value} to {to_status.value}."
        )
# =============================================================
# Helpers
# =============================================================
def _generate_order_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    body = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"QC-{body}"
def _generate_otp() -> str:
    return f"{secrets.randbelow(10000):04d}"
async def _load_order_with_relations(
    db: AsyncSession, order_id: uuid.UUID
) -> Order:
    """Re-fetch an order with items + events eager-loaded.
    Used after any UPDATE to avoid lazy loads in async context.
    """
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.items),
            selectinload(Order.events),
            selectinload(Order.payments),
        )
    )
    return (await db.execute(stmt)).scalar_one()
# =============================================================
# Checkout
# =============================================================
async def place_order(
    db: AsyncSession,
    *,
    user: User,
    address_id: uuid.UUID,
    slot_type: SlotType,
    scheduled_at: datetime | None,
    customer_note: str | None,
    payment_method: str,
    idempotency_key: str | None,
) -> Order:
    # 0. Idempotency â€” same key returns the same order
    if idempotency_key:
        existing = (
            await db.execute(
                select(Order).where(Order.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await _load_order_with_relations(db, existing.id)
    # 1. Validate slot
    if slot_type == SlotType.SCHEDULED and scheduled_at is None:
        raise ValidationError("scheduled_at is required for scheduled delivery.")
    if slot_type == SlotType.EXPRESS and scheduled_at is not None:
        raise ValidationError("scheduled_at must not be set for express delivery.")
    # 2. Validate address
    address = (
        await db.execute(
            select(Address).where(
                Address.id == address_id, Address.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if address is None:
        raise NotFoundError("Delivery address not found.")
    # 3. Load active cart with items
    cart = (
        await db.execute(
            select(Cart)
            .where(Cart.user_id == user.id, Cart.is_active.is_(True))
            .options(
                selectinload(Cart.items).selectinload(CartItem.product),
                selectinload(Cart.shop),
            )
        )
    ).scalars().first()
    if cart is None or not cart.items:
        raise ValidationError("Your cart is empty.")
    shop: Shop = cart.shop
    if not shop.is_open or not shop.is_active:
        raise ConflictError(f"{shop.name} is not accepting orders right now.")
    # 4. Money
    subtotal = sum(
        (item.product.price * item.quantity for item in cart.items),
        start=Decimal("0.00"),
    )
    if subtotal < shop.min_order_value:
        raise ValidationError(
            f"Minimum order value for {shop.name} is Rs.{shop.min_order_value}."
        )
    delivery_fee = shop.delivery_fee
    discount = Decimal("0.00")
    tax = Decimal("0.00")
    total = subtotal + delivery_fee - discount + tax
    # 5. Create order
    order = Order(
        code=_generate_order_code(),
        customer_id=user.id,
        shop_id=shop.id,
        delivery_label=address.label,
        delivery_line1=address.line1,
        delivery_line2=address.line2,
        delivery_landmark=address.landmark,
        delivery_city=address.city,
        delivery_state=address.state,
        delivery_pincode=address.pincode,
        delivery_latitude=address.latitude,
        delivery_longitude=address.longitude,
        delivery_phone=user.phone,
        slot_type=slot_type,
        scheduled_at=scheduled_at,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        discount=discount,
        tax=tax,
        total=total,
        status=OrderStatus.PLACED,
        delivery_otp=_generate_otp(),
        customer_note=customer_note,
        idempotency_key=idempotency_key,
    )
    db.add(order)
    await db.flush()
    # 6. Order items + inventory transfer
    for item in cart.items:
        product = item.product
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_unit=product.unit,
                product_image_url=product.image_url,
                quantity=item.quantity,
                unit_price=product.price,
                line_total=product.price * item.quantity,
            )
        )
        result = await db.execute(
            update(Inventory)
            .where(
                Inventory.product_id == product.id,
                Inventory.reserved_qty >= item.quantity,
            )
            .values(
                stock_qty=Inventory.stock_qty - item.quantity,
                reserved_qty=Inventory.reserved_qty - item.quantity,
            )
        )
        if result.rowcount != 1:
            raise ConflictError(
                f"Stock for {product.name} changed during checkout. "
                "Please review your cart and try again."
            )
    # 7. First OrderEvent
    db.add(
        OrderEvent(
            order_id=order.id,
            actor_id=user.id,
            actor_role=user.role.value,
            from_status=None,
            to_status=OrderStatus.PLACED,
            note="Order placed by customer.",
        )
    )
    # 8. Payment row
    method = PaymentMethod(payment_method)
    db.add(
        Payment(
            order_id=order.id,
            method=method,
            status=PaymentStatus.PENDING,
            amount=total,
        )
    )
    # 9. Deactivate cart + delete items
    await db.execute(sa_delete(CartItem).where(CartItem.cart_id == cart.id))
    cart.is_active = False
    # 10. Notification outbox
    db.add(
        Notification(
            user_id=user.id,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            event_type="order.placed",
            title="Order placed",
            body=f"Your order {order.code} from {shop.name} has been placed.",
            payload=f'{{"order_code":"{order.code}"}}',
        )
    )
    await db.commit()
    return await _load_order_with_relations(db, order.id)
# =============================================================
# Reads
# =============================================================
async def get_order_by_code(
    db: AsyncSession, *, code: str, user: User
) -> Order | None:
    stmt = (
        select(Order)
        .where(Order.code == code)
        .options(
        selectinload(Order.items),
        selectinload(Order.events),
        selectinload(Order.payments),
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        return None
    if user.role not in (
        UserRole.ADMIN,
        UserRole.SHOP_OWNER,
        UserRole.DELIVERY_PARTNER,
    ):
        if order.customer_id != user.id:
            return None
    return order
async def list_customer_orders(
    db: AsyncSession,
    *,
    user: User,
    status_filter: OrderStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OrderSummaryOut], int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    base = select(Order).where(Order.customer_id == user.id)
    if status_filter is not None:
        base = base.where(Order.status == status_filter)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    stmt = (
        base.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .options(selectinload(Order.items))
    )
    orders = (await db.execute(stmt)).scalars().all()
    items_out = [
        OrderSummaryOut(
            id=o.id,
            code=o.code,
            status=o.status,
            shop_id=o.shop_id,
            total=o.total,
            item_count=sum(i.quantity for i in o.items),
            created_at=o.created_at,
        )
        for o in orders
    ]
    return items_out, total
# =============================================================
# Cancel
# =============================================================
async def cancel_order(
    db: AsyncSession,
    *,
    user: User,
    code: str,
    reason: str | None,
) -> Order:
    stmt = (
        select(Order)
        .where(Order.code == code)
        .options(
            selectinload(Order.items),
            selectinload(Order.events),
            selectinload(Order.payments),
        )
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError(f"Order {code} not found.")
    if order.customer_id != user.id:
        raise NotFoundError(f"Order {code} not found.")
    _check_transition(order.status, OrderStatus.CANCELLED)
    for item in order.items:
        await db.execute(
            update(Inventory)
            .where(Inventory.product_id == item.product_id)
            .values(stock_qty=Inventory.stock_qty + item.quantity)
        )
    previous = order.status
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.now(timezone.utc)
    order.cancellation_reason = reason
    db.add(
        OrderEvent(
            order_id=order.id,
            actor_id=user.id,
            actor_role=user.role.value,
            from_status=previous,
            to_status=OrderStatus.CANCELLED,
            note=reason or "Cancelled by customer.",
        )
    )
    db.add(
        Notification(
            user_id=user.id,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            event_type="order.cancelled",
            title="Order cancelled",
            body=f"Order {order.code} was cancelled.",
        )
    )
    order_id = order.id
    await db.commit()
    return await _load_order_with_relations(db, order_id)