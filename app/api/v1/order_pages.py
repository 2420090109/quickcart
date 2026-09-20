"""Order history + detail HTML routes."""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.templating import templates
from app.db.session import get_db
from app.services import order_service
logger = logging.getLogger(__name__)
router = APIRouter(tags=["order-pages"])
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
@router.get("/orders", response_class=HTMLResponse, include_in_schema=False)
async def orders_list(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    user = _require_user(request)
    items, _total = await order_service.list_customer_orders(
        db, user=user, page=1, page_size=50
    )
    return templates.TemplateResponse(
        "orders/list.html", _ctx(request, orders=items)
    )
@router.get("/orders/{code}", response_class=HTMLResponse, include_in_schema=False)
async def order_detail(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    user = _require_user(request)
    order = await order_service.get_order_by_code(db, code=code, user=user)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse(
        "orders/detail.html", _ctx(request, order=order)
    )



@router.get("/orders/{code}/tracking", response_class=HTMLResponse, include_in_schema=False)
async def order_tracking_partial(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    """HTMX partial — returns just the status + timeline block for polling."""
    user = _require_user(request)
    order = await order_service.get_order_by_code(db, code=code, user=user)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse(
        "orders/_tracking.html", _ctx(request, order=order)
    )