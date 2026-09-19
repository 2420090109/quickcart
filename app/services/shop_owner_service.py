"""Shop owner service — order management for a shop.
Reuses the state machine from order_service (LEGAL_TRANSITIONS +
_check_transition) so transitions stay consistent across customer and
shop-owner flows.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import ConflictError, NotFoundError, PermissionError_
from app.models.enums import (
    NotificationChannel,
    NotificationStatus,
    OrderStatus,
)
from app.models.notification import Notification
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.shop import Shop
from app.models.user import User
from app.services.order_service import _check_transition
from app.schemas.shop_owner import ShopOrderListOut, ShopOrderOut
async def _get_owned_shop(db: AsyncSession, owner: User) -> Shop:
    """Return the shop owned by this user. Raise if none / multiple."""
    stmt = select(Shop).where(Shop.owner_id == owner.id, Shop.is_active.is_(True))
    shops = (await db.execute(stmt)).scalars().all()
    if not shops:
        raise PermissionError_("You don't own any active shop.")
    if len(shops) > 1:
        raise PermissionError_(
            "You own multiple shops. Multi-shop mode not implemented yet."
        )
    return shops[0]
async def _load_order_for_shop(
    db: AsyncSession, *, shop_id: uuid.UUID, code: str
) -> Order:
    """Load an order belonging to this shop, with items + events."""
    stmt = (
        select(Order)
        .where(Order.code == code, Order.shop_id == shop_id)
        .options(selectinload(Order.items), selectinload(Order.events))
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise NotFoundError(f"Order {code} not found for your shop.")
    return order
async def _transition(
    db: AsyncSession,
    *,
    order: Order,
    new_status: OrderStatus,
    actor: User,
    note: str | None,
) -> Order:
    """Apply a legal state transition + log the event + notify customer."""
    _check_transition(order.status, new_status)
    previous = order.status
    order.status = new_status
    if new_status == OrderStatus.ACCEPTED:
        order.accepted_at = datetime.now(timezone.utc)
    elif new_status == OrderStatus.DELIVERED:
        order.delivered_at = datetime.now(timezone.utc)
    elif new_status == OrderStatus.CANCELLED:
        order.cancelled_at = datetime.now(timezone.utc)
    db.add(
        OrderEvent(
            order_id=order.id,
            actor_id=actor.id,
            actor_role=actor.role.value,
            from_status=previous,
            to_status=new_status,
            note=note,
        )
    )
    db.add(
        Notification(
            user_id=order.customer_id,
            channel=NotificationChannel.IN_APP,
            status=NotificationStatus.QUEUED,
            event_type=f"order.{new_status.value}",
            title=f"Order {new_status.value}",
            body=f"Your order {order.code} is now {new_status.value}.",
            payload=f'{{"order_code":"{order.code}"}}',
        )
    )
    return order
async def list_shop_orders(
    db: AsyncSession,
    *,
    owner: User,
    status_filter: OrderStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ShopOrderListOut:
    shop = await _get_owned_shop(db, owner)
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    base = select(Order).where(Order.shop_id == shop.id)
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
    return ShopOrderListOut(
        items=[ShopOrderOut.model_validate(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
    )
async def accept_order(
    db: AsyncSession, *, owner: User, code: str
) -> ShopOrderOut:
    shop = await _get_owned_shop(db, owner)
    order = await _load_order_for_shop(db, shop_id=shop.id, code=code)
    await _transition(
        db,
        order=order,
        new_status=OrderStatus.ACCEPTED,
        actor=owner,
        note="Shop accepted the order.",
    )
    order_id = order.id
    await db.commit()
    return await _reload(db, order_id)
async def reject_order(
    db: AsyncSession, *, owner: User, code: str, reason: str
) -> ShopOrderOut:
    shop = await _get_owned_shop(db, owner)
    order = await _load_order_for_shop(db, shop_id=shop.id, code=code)
    await _transition(
        db,
        order=order,
        new_status=OrderStatus.REJECTED,
        actor=owner,
        note=f"Rejected by shop: {reason}",
    )
    order.cancellation_reason = reason
    order_id = order.id
    await db.commit()
    return await _reload(db, order_id)
async def mark_packing(
    db: AsyncSession, *, owner: User, code: str
) -> ShopOrderOut:
    shop = await _get_owned_shop(db, owner)
    order = await _load_order_for_shop(db, shop_id=shop.id, code=code)
    await _transition(
        db,
        order=order,
        new_status=OrderStatus.PACKING,
        actor=owner,
        note="Shop is preparing the order.",
    )
    order_id = order.id
    await db.commit()
    return await _reload(db, order_id)
async def mark_packed(
    db: AsyncSession, *, owner: User, code: str
) -> ShopOrderOut:
    shop = await _get_owned_shop(db, owner)
    order = await _load_order_for_shop(db, shop_id=shop.id, code=code)
    await _transition(
        db,
        order=order,
        new_status=OrderStatus.PACKED,
        actor=owner,
        note="Order packed and ready for pickup.",
    )
    order_id = order.id
    await db.commit()
    return await _reload(db, order_id)
async def _reload(db: AsyncSession, order_id: uuid.UUID) -> ShopOrderOut:
    """Re-fetch with eager loading so serialization never lazy-loads."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
    )
    order = (await db.execute(stmt)).scalar_one()
    return ShopOrderOut.model_validate(order)