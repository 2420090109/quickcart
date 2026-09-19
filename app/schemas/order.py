"""Order schemas — request/response shapes for checkout and order history."""
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import OrderStatus, SlotType
# --- Requests ---
class PlaceOrderRequest(BaseModel):
    """Customer submits this at checkout."""
    address_id: uuid.UUID = Field(..., description="Saved delivery address id")
    slot_type: SlotType = SlotType.EXPRESS
    scheduled_at: datetime | None = Field(
        None, description="Required if slot_type is 'scheduled'"
    )
    customer_note: str | None = Field(None, max_length=500)
    payment_method: str = Field(
        "cod", description="cod | razorpay | wallet (only cod works today)"
    )
class CancelOrderRequest(BaseModel):
    reason: str | None = Field(None, max_length=300)
# --- Responses ---
class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_unit: str
    product_image_url: str | None = None
    quantity: int
    unit_price: Decimal
    line_total: Decimal
class OrderEventOut(BaseModel):
    """One entry in the order timeline."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    from_status: OrderStatus | None = None
    to_status: OrderStatus
    actor_role: str | None = None
    note: str | None = None
    created_at: datetime
class OrderOut(BaseModel):
    """Full order detail — used for both checkout response and history."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    status: OrderStatus
    customer_id: uuid.UUID
    shop_id: uuid.UUID
    # Delivery address snapshot
    delivery_label: str
    delivery_line1: str
    delivery_line2: str | None = None
    delivery_landmark: str | None = None
    delivery_city: str
    delivery_state: str
    delivery_pincode: str
    delivery_latitude: Decimal
    delivery_longitude: Decimal
    delivery_phone: str
    slot_type: SlotType
    scheduled_at: datetime | None = None
    subtotal: Decimal
    delivery_fee: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    customer_note: str | None = None
    cancellation_reason: str | None = None
    delivery_otp: str
    accepted_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut]
    events: list[OrderEventOut] = []
class OrderSummaryOut(BaseModel):
    """Lightweight row for order history listing."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    status: OrderStatus
    shop_id: uuid.UUID
    total: Decimal
    item_count: int
    created_at: datetime
class OrderListOut(BaseModel):
    items: list[OrderSummaryOut]
    total: int
    page: int
    page_size: int