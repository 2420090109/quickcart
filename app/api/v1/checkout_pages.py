"""Checkout HTML routes — cookie-session authenticated."""
import logging
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainError
from app.core.templating import templates
from app.db.session import get_db
from app.models.address import Address
from app.models.enums import SlotType
from app.services import cart_service, order_service
logger = logging.getLogger(__name__)
router = APIRouter(tags=["checkout-pages"])
def _ctx(request: Request, **extra):
    return {
        "request": request,
        "current_user": getattr(request.state, "current_user", None),
        **extra,
    }
def _require_user(request: Request):
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user
@router.get("/checkout", response_class=HTMLResponse, include_in_schema=False)
async def checkout_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    user = _require_user(request)
    cart = await cart_service.get_cart(db, user_id=user.id)
    if cart is None or not cart.items:
        return RedirectResponse(url="/shops", status_code=303)
    addresses = (
        await db.execute(
            select(Address)
            .where(Address.user_id == user.id)
            .order_by(Address.is_default.desc(), Address.created_at.desc())
        )
    ).scalars().all()
    return templates.TemplateResponse(
        "checkout/index.html",
        _ctx(request, cart=cart, addresses=addresses),
    )
@router.post("/checkout/address", response_class=HTMLResponse, include_in_schema=False)
async def create_address(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    label: Annotated[str, Form()],
    line1: Annotated[str, Form()],
    city: Annotated[str, Form()],
    state: Annotated[str, Form()],
    pincode: Annotated[str, Form()],
    latitude: Annotated[float, Form()] = 12.9352,
    longitude: Annotated[float, Form()] = 77.6245,
) -> HTMLResponse:
    user = _require_user(request)
    addr = Address(
        user_id=user.id,
        label=label.strip(),
        line1=line1.strip(),
        city=city.strip(),
        state=state.strip(),
        pincode=pincode.strip(),
        latitude=latitude,
        longitude=longitude,
        is_default=False,
    )
    db.add(addr)
    await db.commit()
    await db.refresh(addr)
    addresses = (
        await db.execute(
            select(Address)
            .where(Address.user_id == user.id)
            .order_by(Address.created_at.desc())
        )
    ).scalars().all()
    return templates.TemplateResponse(
        "checkout/_address_list.html",
        _ctx(request, addresses=addresses, selected_id=addr.id),
    )
@router.post("/checkout/place", include_in_schema=False)
async def place_order(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    address_id: Annotated[str, Form()],
    slot_type: Annotated[str, Form()] = "express",
    payment_method: Annotated[str, Form()] = "cod",
    customer_note: Annotated[str, Form()] = "",
):
    user = _require_user(request)
    try:
        aid = uuid.UUID(address_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid address.")
    try:
        st = SlotType(slot_type)
    except ValueError:
        st = SlotType.EXPRESS
    try:
        order = await order_service.place_order(
            db,
            user=user,
            address_id=aid,
            slot_type=st,
            scheduled_at=None,
            customer_note=customer_note.strip() or None,
            payment_method=payment_method,
            idempotency_key=None,
        )
    except DomainError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return RedirectResponse(url=f"/orders/{order.code}", status_code=303)