"""Payment endpoints — customer-facing.
  POST /orders/{code}/payment/initiate
    Creates a Razorpay order for an existing QuickCart order.
    Client uses the returned razorpay_order_id to open Razorpay Checkout.
  POST /orders/{code}/payment/verify
    After checkout modal returns, the client posts the three signed fields.
    We verify the HMAC and mark the payment PAID.
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import CurrentUser
from app.core.exceptions import DomainError
from app.db.session import get_db
from app.schemas.payment import (
    PaymentInitiateOut,
    PaymentOut,
    PaymentVerifyIn,
)
from app.services import payment_service
router = APIRouter(tags=["payments"])
def _translate(e: DomainError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)
@router.post(
    "/orders/{code}/payment/initiate",
    response_model=PaymentInitiateOut,
    summary="Create a Razorpay order for this QuickCart order",
)
async def initiate(
    code: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentInitiateOut:
    try:
        return await payment_service.initiate_payment(db, user=user, code=code)
    except DomainError as e:
        raise _translate(e) from e
@router.post(
    "/orders/{code}/payment/verify",
    response_model=PaymentOut,
    summary="Verify Razorpay checkout signature and mark paid",
)
async def verify(
    code: str,
    data: PaymentVerifyIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentOut:
    try:
        return await payment_service.verify_checkout_and_mark_paid(
            db,
            user=user,
            code=code,
            razorpay_order_id=data.razorpay_order_id,
            razorpay_payment_id=data.razorpay_payment_id,
            razorpay_signature=data.razorpay_signature,
        )
    except DomainError as e:
        raise _translate(e) from e