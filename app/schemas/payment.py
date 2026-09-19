"""Payment schemas."""
import uuid
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import PaymentMethod, PaymentStatus
class PaymentInitiateOut(BaseModel):
    """Returned to the client so it can open Razorpay Checkout."""
    razorpay_order_id: str
    razorpay_key_id: str
    amount: int = Field(..., description="Amount in paise (₹1 = 100 paise)")
    currency: str = "INR"
    order_code: str
    customer_name: str
    customer_phone: str
    description: str
class PaymentVerifyIn(BaseModel):
    """Client sends this after Razorpay Checkout returns."""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
class PaymentOut(BaseModel):
    """Public view of a payment row."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_id: uuid.UUID
    method: PaymentMethod
    status: PaymentStatus
    amount: Decimal
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    failure_reason: str | None = None