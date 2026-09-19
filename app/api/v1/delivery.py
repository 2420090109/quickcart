"""Delivery partner routes.
All endpoints require DELIVERY_PARTNER role.
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import require_role
from app.core.exceptions import DomainError
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.delivery import (
    DeliverOrderRequest,
    DeliveryAssignmentListOut,
    DeliveryAssignmentOut,
    DeliveryOrderListOut,
    DeliveryOrderOut,
    LocationOut,
    UpdateLocationRequest,
)
from app.services import delivery_service
router = APIRouter(prefix="/delivery", tags=["delivery"])
Partner = Annotated[User, Depends(require_role(UserRole.DELIVERY_PARTNER))]
def _translate(e: DomainError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)
@router.get(
    "/orders/available",
    response_model=DeliveryOrderListOut,
    summary="List packed orders waiting for pickup",
)
async def list_available(
    partner: Partner,
    db: Annotated[AsyncSession, Depends(get_db)],
    pincode: str | None = Query(None, description="Filter by delivery pincode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> DeliveryOrderListOut:
    return await delivery_service.list_available_orders(
        db, partner=partner, pincode=pincode, page=page, page_size=page_size
    )
@router.post(
    "/orders/{code}/accept",
    response_model=DeliveryAssignmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Claim a packed order for delivery",
)
async def accept_assignment(
    code: str,
    partner: Partner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeliveryAssignmentOut:
    try:
        return await delivery_service.accept_assignment(db, partner=partner, code=code)
    except DomainError as e:
        raise _translate(e) from e
@router.get(
    "/assignments",
    response_model=DeliveryAssignmentListOut,
    summary="List my delivery assignments",
)
async def list_assignments(
    partner: Partner,
    db: Annotated[AsyncSession, Depends(get_db)],
    only_active: bool = Query(True, description="Only show active assignments"),
) -> DeliveryAssignmentListOut:
    return await delivery_service.list_my_assignments(
        db, partner=partner, only_active=only_active
    )
@router.post(
    "/orders/{code}/pickup",
    response_model=DeliveryOrderOut,
    summary="Mark order as physically picked up from the shop",
)
async def pickup(
    code: str,
    partner: Partner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeliveryOrderOut:
    try:
        return await delivery_service.pickup_order(db, partner=partner, code=code)
    except DomainError as e:
        raise _translate(e) from e
@router.post(
    "/orders/{code}/deliver",
    response_model=DeliveryOrderOut,
    summary="Verify OTP and mark the order delivered",
)
async def deliver(
    code: str,
    data: DeliverOrderRequest,
    partner: Partner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeliveryOrderOut:
    try:
        return await delivery_service.deliver_order(
            db, partner=partner, code=code, otp=data.otp
        )
    except DomainError as e:
        raise _translate(e) from e
@router.post(
    "/location",
    response_model=LocationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Push my GPS location",
)
async def push_location(
    data: UpdateLocationRequest,
    partner: Partner,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LocationOut:
    try:
        return await delivery_service.push_location(
            db,
            partner=partner,
            latitude=data.latitude,
            longitude=data.longitude,
            accuracy_m=data.accuracy_m,
            order_code=data.order_code,
        )
    except DomainError as e:
        raise _translate(e) from e