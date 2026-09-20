"""Shop owner dashboard — HTML routes."""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import DomainError
from app.core.templating import templates
from app.db.session import get_db
from app.models.enums import OrderStatus, UserRole
from app.models.order import Order
from app.models.shop import Shop
from app.models.user import User
from app.services import shop_owner_service
logger = logging.getLogger(__name__)
router = APIRouter(tags=["shop-owner-pages"])
def _ctx(request: Request, **extra):
    return {
        "request": request,
        "current_user": getattr(request.state, "current_user", None),
        **extra,
    }
def _require_shop_owner(request: Request) -> User:
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    if user.role != UserRole.SHOP_OWNER:
        raise HTTPException(status_code=403, detail="Shop owner only.")
    return user
async def _get_owned_shop(db: AsyncSession, owner: User) -> Shop:
    stmt = select(Shop).where(Shop.owner_id == owner.id, Shop.is_active.is_(True))
    shop = (await db.execute(stmt)).scalars().first()
    if shop is None:
        raise HTTPException(status_code=404, detail="You don't own any shop.")
    return shop
async def _dashboard_ctx(db: AsyncSession, owner: User, status_filter: str) -> dict:
    shop = await _get_owned_shop(db, owner)
    today_start = func.date_trunc("day", func.now())
    stats_stmt = (
        select(
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total), 0).label("total_revenue"),
        )
        .where(
            Order.shop_id == shop.id,
            Order.created_at >= today_start,
            Order.status.notin_([OrderStatus.REJECTED, OrderStatus.CANCELLED]),
        )
    )
    stats_row = (await db.execute(stats_stmt)).first()
    total_orders = stats_row.total_orders or 0
    total_revenue = stats_row.total_revenue or 0
    stmt = (
        select(Order)
        .where(Order.shop_id == shop.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    if status_filter == "new":
        stmt = stmt.where(Order.status == OrderStatus.PLACED)
    elif status_filter == "in_progress":
        stmt = stmt.where(
            Order.status.in_([
                OrderStatus.ACCEPTED,
                OrderStatus.PACKING,
                OrderStatus.PACKED,
                OrderStatus.OUT_FOR_DELIVERY,
            ])
        )
    elif status_filter == "completed":
        stmt = stmt.where(
            Order.status.in_([
                OrderStatus.DELIVERED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.REFUNDED,
            ])
        )
    stmt = stmt.limit(100)
    orders = (await db.execute(stmt)).scalars().all()
    counts_stmt = (
        select(Order.status, func.count(Order.id))
        .where(Order.shop_id == shop.id)
        .group_by(Order.status)
    )
    status_counts = {row[0]: row[1] for row in (await db.execute(counts_stmt)).all()}
    new_count = status_counts.get(OrderStatus.PLACED, 0)
    in_progress_count = sum(
        status_counts.get(s, 0)
        for s in (OrderStatus.ACCEPTED, OrderStatus.PACKING, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY)
    )
    completed_count = sum(
        status_counts.get(s, 0)
        for s in (OrderStatus.DELIVERED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.REFUNDED)
    )
    return {
        "shop": shop,
        "orders": orders,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "filter": status_filter,
        "new_count": new_count,
        "in_progress_count": in_progress_count,
        "completed_count": completed_count,
    }
@router.get("/shop-dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    filter: str = Query("new"),
) -> HTMLResponse:
    owner = _require_shop_owner(request)
    ctx = await _dashboard_ctx(db, owner, filter)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("shop_owner/_queue.html", _ctx(request, **ctx))
    return templates.TemplateResponse("shop_owner/dashboard.html", _ctx(request, **ctx))
@router.post("/shop-dashboard/orders/{code}/accept", response_class=HTMLResponse, include_in_schema=False)
async def accept(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    owner = _require_shop_owner(request)
    try:
        await shop_owner_service.accept_order(db, owner=owner, code=code)
    except DomainError:
        pass
    ctx = await _dashboard_ctx(db, owner, "in_progress")
    return templates.TemplateResponse("shop_owner/_queue.html", _ctx(request, **ctx))
@router.post("/shop-dashboard/orders/{code}/reject", response_class=HTMLResponse, include_in_schema=False)
async def reject(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    reason: Annotated[str, Form()] = "Unavailable",
) -> HTMLResponse:
    owner = _require_shop_owner(request)
    try:
        await shop_owner_service.reject_order(db, owner=owner, code=code, reason=reason)
    except DomainError:
        pass
    ctx = await _dashboard_ctx(db, owner, "new")
    return templates.TemplateResponse("shop_owner/_queue.html", _ctx(request, **ctx))
@router.post("/shop-dashboard/orders/{code}/packing", response_class=HTMLResponse, include_in_schema=False)
async def packing(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    owner = _require_shop_owner(request)
    try:
        await shop_owner_service.mark_packing(db, owner=owner, code=code)
    except DomainError:
        pass
    ctx = await _dashboard_ctx(db, owner, "in_progress")
    return templates.TemplateResponse("shop_owner/_queue.html", _ctx(request, **ctx))
@router.post("/shop-dashboard/orders/{code}/packed", response_class=HTMLResponse, include_in_schema=False)
async def packed(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    owner = _require_shop_owner(request)
    try:
        await shop_owner_service.mark_packed(db, owner=owner, code=code)
    except DomainError:
        pass
    ctx = await _dashboard_ctx(db, owner, "in_progress")
    return templates.TemplateResponse("shop_owner/_queue.html", _ctx(request, **ctx))