"""Razorpay webhook receiver.
CRITICAL: We read the raw request body, not a parsed Pydantic model.
Razorpay signs the exact bytes they sent. Any transformation (JSON
re-serialization, whitespace changes) breaks the signature.
"""
import json
import logging
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.razorpay import verify_webhook_signature
from app.db.session import get_db
from app.services import payment_service
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])
@router.post(
    "/razorpay",
    summary="Receive Razorpay webhook events (signature-verified)",
)
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_razorpay_signature: str = Header(..., alias="X-Razorpay-Signature"),
) -> dict:
    raw = await request.body()
    if not verify_webhook_signature(raw_body=raw, signature=x_razorpay_signature):
        logger.warning("Rejected Razorpay webhook: bad signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Malformed JSON body.") from e
    event_type = payload.get("event", "unknown")
    logger.info("Razorpay webhook received: %s", event_type)
    return await payment_service.handle_webhook_event(
        db, event_type=event_type, payload=payload
    )