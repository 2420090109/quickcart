"""Schemas for the shop-owner endpoints."""
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import OrderStatus
class ShopOrderItemOut(BaseModel):
    """A line item as the shop owner needs to see it."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_unit: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
class ShopOrderOut(BaseModel):
    """Order view for shop owners — includes customer contact info."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    status: OrderStatus
    customer_id: uuid.UUID
    # Delivery contact
    delivery_label: str
    delivery_line1: str
    delivery_line2: str | None = None
    delivery_landmark: str | None = None
    delivery_city: str
    delivery_pincode: str
    delivery_phone: str
    subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal
    customer_note: str | None = None
    accepted_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    items: list[ShopOrderItemOut]
class ShopOrderListOut(BaseModel):
    items: list[ShopOrderOut]
    total: int
    page: int
    page_size: int
class RejectOrderRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)