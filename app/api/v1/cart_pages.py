"""Cart HTMX endpoints — cookie-session authenticated, returns HTML fragments.
These mirror the JSON API at /api/v1/cart but return HTML partials instead
of JSON. They read the current user from request.state.current_user (set by
AuthMiddleware from the session cookie).
Response format for every mutation:
  - First: the cart drawer HTML (swapped into #cart-drawer-body)
  - Also: OOB swap of the header badge (#cart-badge)
  - Also: OOB swap of an empty toast trigger
"""
import logging
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainError
from app.core.templating import templates
from app.db.session import get_db
from app.schemas.cart import AddCartItemRequest
from app.services import cart_service
logger = logging.getLogger(__name__)
router = APIRouter(tags=["cart-pages"])
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
def _render_cart(request: Request, cart) -> HTMLResponse:
    """Render the drawer body + OOB badge + optional toast."""
    return templates.TemplateResponse(
        "cart/_drawer.html",
        _ctx(request, cart=cart),
    )
@router.get("/cart/drawer", response_class=HTMLResponse, include_in_schema=False)
async def get_drawer(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    user = _require_user(request)
    cart = await cart_service.get_cart(db, user_id=user.id)
    return _render_cart(request, cart)
@router.post("/cart/add", response_class=HTMLResponse, include_in_schema=False)
async def add_to_cart(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    product_id: Annotated[str, Form()],
    quantity: Annotated[int, Form()] = 1,
) -> HTMLResponse:
    user = _require_user(request)
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product id.")
    try:
        cart = await cart_service.add_to_cart(
            db,
            user_id=user.id,
            data=AddCartItemRequest(product_id=pid, quantity=quantity),
        )
    except DomainError as e:
        # Return a fragment with just the error toast, no cart change
        return HTMLResponse(
            f'<div class="hidden" hx-on:load="window.toast(\'{e.message}\', \'error\')"></div>'
        )
    return _render_cart(request, cart)
@router.post("/cart/update", response_class=HTMLResponse, include_in_schema=False)
async def update_cart(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: Annotated[str, Form()],
    quantity: Annotated[int, Form()],
) -> HTMLResponse:
    user = _require_user(request)
    try:
        iid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item id.")
    try:
        cart = await cart_service.update_cart_item(
            db, user_id=user.id, item_id=iid, new_quantity=quantity
        )
    except DomainError as e:
        return HTMLResponse(
            f'<div class="hidden" hx-on:load="window.toast(\'{e.message}\', \'error\')"></div>'
        )
    return _render_cart(request, cart)
@router.post("/cart/remove", response_class=HTMLResponse, include_in_schema=False)
async def remove_item(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    item_id: Annotated[str, Form()],
) -> HTMLResponse:
    user = _require_user(request)
    try:
        iid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item id.")
    try:
        cart = await cart_service.remove_cart_item(db, user_id=user.id, item_id=iid)
    except DomainError as e:
        return HTMLResponse(
            f'<div class="hidden" hx-on:load="window.toast(\'{e.message}\', \'error\')"></div>'
        )
    return _render_cart(request, cart)
@router.post("/cart/clear", response_class=HTMLResponse, include_in_schema=False)
async def clear_cart(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    user = _require_user(request)
    await cart_service.clear_cart(db, user_id=user.id)
    return _render_cart(request, None)