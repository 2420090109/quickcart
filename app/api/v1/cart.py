"""Cart routes — all require an authenticated customer."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import CurrentUser
from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.db.session import get_db
from app.schemas.cart import (
    AddCartItemRequest,
    CartOut,
    UpdateCartItemRequest,
)
from app.services import cart_service
router = APIRouter(prefix="/cart", tags=["cart"])
def _translate(e: DomainError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)
@router.get(
    "",
    response_model=CartOut | None,
    summary="Get my active cart",
)
async def get_my_cart(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut | None:
    return await cart_service.get_cart(db, user_id=user.id)
@router.post(
    "/items",
    response_model=CartOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product to the cart",
)
async def add_item(
    data: AddCartItemRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut:
    try:
        return await cart_service.add_to_cart(db, user_id=user.id, data=data)
    except DomainError as e:
        raise _translate(e) from e
@router.patch(
    "/items/{item_id}",
    response_model=CartOut,
    summary="Change quantity of a cart line",
)
async def update_item(
    item_id: str,
    data: UpdateCartItemRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut:
    import uuid as _uuid
    try:
        item_uuid = _uuid.UUID(item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid item id.") from e
    try:
        return await cart_service.update_cart_item(
            db, user_id=user.id, item_id=item_uuid, new_quantity=data.quantity
        )
    except DomainError as e:
        raise _translate(e) from e
@router.delete(
    "/items/{item_id}",
    response_model=CartOut,
    summary="Remove a cart line",
)
async def delete_item(
    item_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CartOut:
    import uuid as _uuid
    try:
        item_uuid = _uuid.UUID(item_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid item id.") from e
    try:
        return await cart_service.remove_cart_item(
            db, user_id=user.id, item_id=item_uuid
        )
    except DomainError as e:
        raise _translate(e) from e
@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear my entire cart",
)
async def clear(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await cart_service.clear_cart(db, user_id=user.id)