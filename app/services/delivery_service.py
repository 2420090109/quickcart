"""Delivery partner service.
Handles the final leg of the order lifecycle:
    PACKED  ──►  OUT_FOR_DELIVERY  ──►  DELIVERED
       │                 │
       │                 └── pickup by partner
       └── assignment created when partner accepts
The OTP check at delivery is the critical proof: the customer shares a
4-digit code shown on their order, the partner enters it. Only a correct
OTP can move the order to DELIVERED. This prevents "phantom deliveries".
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionError_,
    ValidationError,
)
from app.models.delivery_assignment import DeliveryAssignment
from app.models.delivery_location import DeliveryLocation
from app.models.enums import (
    DeliveryAssignmentStatus,
    NotificationChannel,
    NotificationStatus,
    OrderStatus,
)
from app.models.notification import Notification
from app.models.order import Order
from app.models.order_event import OrderEvent
from app.models.user import User
from app.services.order_service import _check_transition
from app.schemas.delivery import (
    DeliveryAssignmentOut,
    DeliveryAssignmentListOut,
    DeliveryOrderListOut,
    DeliveryOrderOut,
    LocationOut,
)
# =============================================================
# Helpers
# =============================================================
async def _reload_order(db: AsyncSession, order_id: uuid.UUID) -> Order:
    stmt = select(Order).where(Order.id == order_id)
    return (await db.execute(stmt)).scalar_one()
async def _load_active_assignment(
    db: AsyncSession, *, order_id: uuid.UUID
) -> DeliveryAssignment | None:
    """Find the active (non-terminal) assignment for an order, if any."""
    active_states = (
        DeliveryAssignmentStatus.ASSIGNED,
        DeliveryAssignmentStatus.ACCEPTED,
        DeliveryAssignmentStatus.PICKED_UP,
    )
    stmt = select(DeliveryAssignment).where(
        DeliveryAssignment.order_id == order_id,
        DeliveryAssignment.status.in_(active_states),
    )
    return (await db.execute(stmt)).scalar_one_or_none()
async def _log_transition(
    db: AsyncSession,
    *,
    order: Order,
    new_status: OrderStatus,
    actor: User,
    note: str,
) -> None:
    _check_transition(order.status, new_status)
    previous = order.status
    order.status = new_status
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
# =============================================================
# Public: list available orders
# =============================================================
async def list_available_orders(
    db: AsyncSession,
    *,
    partner: User,
    pincode: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> DeliveryOrderListOut:
    """Return PACKED orders with no active assignment.
    Delivery partners browse this list, then call /accept to claim one.
    Optional pincode filter lets a partner restrict to their area.
    """
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    # Orders that are PACKED and don't have any active assignment
    active_states = (
        DeliveryAssignmentStatus.ASSIGNED,
        DeliveryAssignmentStatus.ACCEPTED,
        DeliveryAssignmentStatus.PICKED_UP,
    )
    subq = (
        select(DeliveryAssignment.order_id)
        .where(DeliveryAssignment.status.in_(active_states))
    )
    base = select(Order).where(
        Order.status == OrderStatus.PACKED,
        Order.id.notin_(subq),
    )
    if pincode:
        base = base.where(Order.delivery_pincode == pincode)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    stmt = (
        base.order_by(Order.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orders = (await db.execute(stmt)).scalars().all()
    return DeliveryOrderListOut(
        items=[DeliveryOrderOut.model_validate(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
    )
# =============================================================
# Public: accept assignment
# =============================================================
async def accept_assignment(
    db: AsyncSession, *, partner: User, code: str
) -> DeliveryAssignmentOut:
    """Claim a PACKED order.
    The partial unique index on delivery_assignments
    (`uq_delivery_assignments_order_active`) guarantees no two partners
    can hold the same order. If two partners race to accept, one wins
    and the other gets a ConflictError.
    """
    order = (
        await db.execute(select(Order).where(Order.code == code))
    ).scalar_one_or_none()
    if order is None:
        raise NotFoundError(f"Order {code} not found.")
    if order.status != OrderStatus.PACKED:
        raise ConflictError(
            f"Order {code} is not available for pickup (status: {order.status.value})."
        )
    existing = await _load_active_assignment(db, order_id=order.id)
    if existing is not None:
        raise ConflictError("This order is already claimed by another partner.")
    assignment = DeliveryAssignment(
        order_id=order.id,
        partner_id=partner.id,
        status=DeliveryAssignmentStatus.ASSIGNED,
    )
    db.add(assignment)
    await db.flush()
    # We don't change order.status yet — pickup does that
    await db.commit()
    return DeliveryAssignmentOut.model_validate(assignment)
# =============================================================
# Public: list my assignments
# =============================================================
async def list_my_assignments(
    db: AsyncSession, *, partner: User, only_active: bool = True
) -> DeliveryAssignmentListOut:
    stmt = select(DeliveryAssignment).where(
        DeliveryAssignment.partner_id == partner.id
    )
    if only_active:
        stmt = stmt.where(
            DeliveryAssignment.status.in_(
                (
                    DeliveryAssignmentStatus.ASSIGNED,
                    DeliveryAssignmentStatus.ACCEPTED,
                    DeliveryAssignmentStatus.PICKED_UP,
                )
            )
        )
    stmt = stmt.order_by(DeliveryAssignment.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return DeliveryAssignmentListOut(
        items=[DeliveryAssignmentOut.model_validate(r) for r in rows],
        total=len(rows),
    )
# =============================================================
# Public: pickup
# =============================================================
async def pickup_order(
    db: AsyncSession, *, partner: User, code: str
) -> DeliveryOrderOut:
    """Mark the order as physically picked up from the shop.
    Transitions:
      Order: PACKED -> OUT_FOR_DELIVERY
      Assignment: ASSIGNED/ACCEPTED -> PICKED_UP
    """
    order = (
        await db.execute(select(Order).where(Order.code == code))
    ).scalar_one_or_none()
    if order is None:
        raise NotFoundError(f"Order {code} not found.")
    assignment = await _load_active_assignment(db, order_id=order.id)
    if assignment is None or assignment.partner_id != partner.id:
        raise PermissionError_("You don't own an active assignment for this order.")
    await _log_transition(
        db,
        order=order,
        new_status=OrderStatus.OUT_FOR_DELIVERY,
        actor=partner,
        note="Picked up by delivery partner.",
    )
    assignment.status = DeliveryAssignmentStatus.PICKED_UP
    assignment.picked_up_at = datetime.now(timezone.utc)
    order_id = order.id
    await db.commit()
    return DeliveryOrderOut.model_validate(await _reload_order(db, order_id))
# =============================================================
# Public: deliver (OTP verification)
# =============================================================
async def deliver_order(
    db: AsyncSession, *, partner: User, code: str, otp: str
) -> DeliveryOrderOut:
    """Verify OTP and mark delivered.
    This is the moment the order becomes terminal. The OTP ensures the
    customer actually received the goods — no fake deliveries.
    """
    order = (
        await db.execute(select(Order).where(Order.code == code))
    ).scalar_one_or_none()
    if order is None:
        raise NotFoundError(f"Order {code} not found.")
    assignment = await _load_active_assignment(db, order_id=order.id)
    if assignment is None or assignment.partner_id != partner.id:
        raise PermissionError_("You don't own an active assignment for this order.")
    # OTP check — timing-safe comparison
    import hmac
    if not hmac.compare_digest(otp.strip(), order.delivery_otp):
        raise ValidationError("Incorrect OTP. Ask the customer for the code.")
    await _log_transition(
        db,
        order=order,
        new_status=OrderStatus.DELIVERED,
        actor=partner,
        note="Delivered and OTP verified.",
    )
    order.delivered_at = datetime.now(timezone.utc)
    assignment.status = DeliveryAssignmentStatus.DELIVERED
    assignment.delivered_at = datetime.now(timezone.utc)
    order_id = order.id
    await db.commit()
    return DeliveryOrderOut.model_validate(await _reload_order(db, order_id))
# =============================================================
# Public: push location
# =============================================================
async def push_location(
    db: AsyncSession,
    *,
    partner: User,
    latitude,
    longitude,
    accuracy_m,
    order_code: str | None,
) -> LocationOut:
    """Record a GPS ping from the partner's device.
    We keep these rows for a short window (24h cleanup later). The latest
    row per (partner, order) drives the customer's tracking map.
    """
    order_id: uuid.UUID | None = None
    if order_code:
        row = (
            await db.execute(select(Order.id).where(Order.code == order_code))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"Order {order_code} not found.")
        order_id = row
    loc = DeliveryLocation(
        partner_id=partner.id,
        order_id=order_id,
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy_m,
    )
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return LocationOut.model_validate(loc)