"""Shop owner routes — order management for a shop.
All endpoints require SHOP_OWNER role. The service layer enforces
"this order must belong to my shop".
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_role
from app.core.exceptions import DomainError
from app.db.session import get_db
from app.models.enums import OrderStatus, UserRole
from app.models.user import User
from app.schemas.shop_owner import (
    RejectOrderRequest,
    ShopOrderListOut,
    ShopOrderOut,
)
from app.services import shop_owner_service
router = APIRouter(prefix="/shop-owner", tags=["shop-owner"])
ShopOwner = Annotated[User, Depends(require_role(UserRole.SHOP_OWNER))]
def _translate(e: DomainError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)
@router.get(
    "/orders",
    response_model=ShopOrderListOut,
    summary="List orders for my shop",
)
async def list_orders(
    owner: ShopOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: OrderStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ShopOrderListOut:
    try:
        return await shop_owner_service.list_shop_orders(
            db,
            owner=owner,
            status_filter=status_filter,
            page=page,
            page_size=page_size,
        )
    except DomainError as e:
        raise _translate(e) from e
@router.post(
    "/orders/{code}/accept",
    response_model=ShopOrderOut,
    summary="Accept a placed order",
)
async def accept_order(
    code: str,
    owner: ShopOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopOrderOut:
    try:
        return await shop_owner_service.accept_order(db, owner=owner, code=code)
    except DomainError as e:
        raise _translate(e) from e
@router.post(
    "/orders/{code}/reject",
    response_model=ShopOrderOut,
    summary="Reject a placed order",
)
async def reject_order(
    code: str,
    data: RejectOrderRequest,
    owner: ShopOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopOrderOut:
    try:
        return await shop_owner_service.reject_order(
            db, owner=owner, code=code, reason=data.reason
        )
    except DomainError as e:
        raise _translate(e) from e
@router.post(
    "/orders/{code}/packing",
    response_model=ShopOrderOut,
    summary="Mark order as being prepared",
)
async def mark_packing(
    code: str,
    owner: ShopOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopOrderOut:
    try:
        return await shop_owner_service.mark_packing(db, owner=owner, code=code)
    except DomainError as e:
        raise _translate(e) from e
@router.post(
    "/orders/{code}/packed",
    response_model=ShopOrderOut,
    summary="Mark order as packed and ready for pickup",
)
async def mark_packed(
    code: str,
    owner: ShopOwner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopOrderOut:
    try:
        return await shop_owner_service.mark_packed(db, owner=owner, code=code)
    except DomainError as e:
        raise _translate(e) from e