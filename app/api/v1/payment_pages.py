"""Cookie-session wrappers for the payment JSON endpoints.
Mirrors /api/v1/orders/{code}/payment/* but reads the current user from
the session cookie instead of an Authorization: Bearer header.
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DomainError
from app.db.session import get_db
from app.schemas.payment import PaymentInitiateOut, PaymentOut, PaymentVerifyIn
from app.services import payment_service
logger = logging.getLogger(__name__)
router = APIRouter(tags=["payment-pages"])
def _require_user(request: Request):
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user
def _translate(e: DomainError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)
@router.post(
    "/payments/{code}/initiate",
    response_model=PaymentInitiateOut,
    include_in_schema=False,
)
async def initiate(
    code: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentInitiateOut:
    user = _require_user(request)
    try:
        return await payment_service.initiate_payment(db, user=user, code=code)
    except DomainError as e:
        raise _translate(e) from e
@router.post(
    "/payments/{code}/verify",
    response_model=PaymentOut,
    include_in_schema=False,
)
async def verify(
    code: str,
    data: PaymentVerifyIn,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentOut:
    user = _require_user(request)
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