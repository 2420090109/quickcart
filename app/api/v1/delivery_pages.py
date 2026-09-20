"""Delivery partner dashboard — HTML routes."""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import DomainError
from app.core.templating import templates
from app.db.session import get_db
from app.models.delivery_assignment import DeliveryAssignment
from app.models.enums import DeliveryAssignmentStatus, UserRole
from app.models.order import Order
from app.models.user import User
from app.services import delivery_service
logger = logging.getLogger(__name__)
router = APIRouter(tags=["delivery-pages"])
def _ctx(request: Request, **extra):
    return {
        "request": request,
        "current_user": getattr(request.state, "current_user", None),
        **extra,
    }
def _require_partner(request: Request) -> User:
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    if user.role != UserRole.DELIVERY_PARTNER:
        raise HTTPException(status_code=403, detail="Delivery partners only.")
    return user
async def _dashboard_ctx(db: AsyncSession, partner: User) -> dict:
    """Available pickups + my active deliveries."""
    # Available — packed orders with no active assignment
    active_states = (
        DeliveryAssignmentStatus.ASSIGNED,
        DeliveryAssignmentStatus.ACCEPTED,
        DeliveryAssignmentStatus.PICKED_UP,
    )
    subq = (
        select(DeliveryAssignment.order_id)
        .where(DeliveryAssignment.status.in_(active_states))
    )
    available = (
        await db.execute(
            select(Order)
            .where(Order.status == "packed", Order.id.notin_(subq))
            .order_by(Order.created_at.asc())
            .limit(30)
        )
    ).scalars().all()
    # My active deliveries
    my_assignments = (
        await db.execute(
            select(DeliveryAssignment)
            .where(
                DeliveryAssignment.partner_id == partner.id,
                DeliveryAssignment.status.in_(active_states),
            )
            .options(selectinload(DeliveryAssignment.order).selectinload(Order.items))
            .order_by(DeliveryAssignment.created_at.desc())
        )
    ).scalars().all()
    return {
        "available": available,
        "my_assignments": my_assignments,
    }
@router.get("/delivery-dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    partner = _require_partner(request)
    ctx = await _dashboard_ctx(db, partner)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("delivery/_dashboard_body.html", _ctx(request, **ctx))
    return templates.TemplateResponse("delivery/dashboard.html", _ctx(request, **ctx))
@router.post("/delivery-dashboard/orders/{code}/accept", response_class=HTMLResponse, include_in_schema=False)
async def accept(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    partner = _require_partner(request)
    try:
        await delivery_service.accept_assignment(db, partner=partner, code=code)
    except DomainError:
        pass
    ctx = await _dashboard_ctx(db, partner)
    return templates.TemplateResponse("delivery/_dashboard_body.html", _ctx(request, **ctx))
@router.post("/delivery-dashboard/orders/{code}/pickup", response_class=HTMLResponse, include_in_schema=False)
async def pickup(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    partner = _require_partner(request)
    try:
        await delivery_service.pickup_order(db, partner=partner, code=code)
    except DomainError:
        pass
    ctx = await _dashboard_ctx(db, partner)
    return templates.TemplateResponse("delivery/_dashboard_body.html", _ctx(request, **ctx))
@router.post("/delivery-dashboard/orders/{code}/deliver", response_class=HTMLResponse, include_in_schema=False)
async def deliver(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    otp: Annotated[str, Form()],
) -> HTMLResponse:
    partner = _require_partner(request)
    error = None
    try:
        await delivery_service.deliver_order(db, partner=partner, code=code, otp=otp.strip())
    except DomainError as e:
        error = e.message
    ctx = await _dashboard_ctx(db, partner)
    ctx["error"] = error
    return templates.TemplateResponse("delivery/_dashboard_body.html", _ctx(request, **ctx))
@router.post("/delivery-dashboard/location", response_class=HTMLResponse, include_in_schema=False)
async def push_location(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    latitude: Annotated[str, Form()] = "12.9352",
    longitude: Annotated[str, Form()] = "77.6245",
    order_code: Annotated[str, Form()] = "",
) -> HTMLResponse:
    partner = _require_partner(request)
    from decimal import Decimal
    try:
        await delivery_service.push_location(
            db,
            partner=partner,
            latitude=Decimal(latitude),
            longitude=Decimal(longitude),
            accuracy_m=Decimal("10"),
            order_code=order_code or None,
        )
    except DomainError:
        pass
    ctx = await _dashboard_ctx(db, partner)
    return templates.TemplateResponse("delivery/_dashboard_body.html", _ctx(request, **ctx))