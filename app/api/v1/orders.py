"""Order routes — checkout, history, detail, cancel."""
from typing import Annotated
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import CurrentUser
from app.core.exceptions import DomainError
from app.db.session import get_db
from app.models.enums import OrderStatus
from app.schemas.order import (
    CancelOrderRequest,
    OrderListOut,
    OrderOut,
    PlaceOrderRequest,
    OrderSummaryOut,
)
from app.services import order_service
router = APIRouter(prefix="/orders", tags=["orders"])
def _translate(e: DomainError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)
@router.post(
    "",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order from the current cart",
)
async def place_order(
    data: PlaceOrderRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Optional. Same key returns the same order.",
        ),
    ] = None,
) -> OrderOut:
    try:
        order = await order_service.place_order(
            db,
            user=user,
            address_id=data.address_id,
            slot_type=data.slot_type,
            scheduled_at=data.scheduled_at,
            customer_note=data.customer_note,
            payment_method=data.payment_method,
            idempotency_key=idempotency_key,
        )
    except DomainError as e:
        raise _translate(e) from e
    return OrderOut.model_validate(order)
@router.get(
    "",
    response_model=OrderListOut,
    summary="List my orders",
)
async def list_my_orders(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: OrderStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> OrderListOut:
    items, total = await order_service.list_customer_orders(
        db,
        user=user,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )
    return OrderListOut(items=items, total=total, page=page, page_size=page_size)
@router.get(
    "/{code}",
    response_model=OrderOut,
    summary="Order detail with event timeline",
)
async def get_order(
    code: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderOut:
    order = await order_service.get_order_by_code(db, code=code, user=user)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {code} not found.",
        )
    return OrderOut.model_validate(order)
@router.post(
    "/{code}/cancel",
    response_model=OrderOut,
    summary="Cancel an order (before delivery)",
)
async def cancel_order(
    code: str,
    data: CancelOrderRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderOut:
    try:
        order = await order_service.cancel_order(
            db, user=user, code=code, reason=data.reason
        )
    except DomainError as e:
        raise _translate(e) from e
    return OrderOut.model_validate(order)