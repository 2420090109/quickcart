"""Delivery partner schemas."""
import uuid
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import DeliveryAssignmentStatus, OrderStatus
# --- Requests ---
class DeliverOrderRequest(BaseModel):
    """Delivery partner submits the customer-shared OTP to complete delivery."""
    otp: str = Field(..., min_length=4, max_length=6)
class UpdateLocationRequest(BaseModel):
    """Delivery partner pushes their GPS location."""
    latitude: Decimal = Field(..., ge=-90, le=90)
    longitude: Decimal = Field(..., ge=-180, le=180)
    accuracy_m: Decimal | None = Field(None, ge=0)
    order_code: str | None = Field(
        None, description="Attach location to a specific in-flight order"
    )
# --- Responses ---
class DeliveryOrderOut(BaseModel):
    """Order view for delivery partners.
    Includes the delivery address and pincode so the partner knows where
    to go. Excludes money and shop-internal fields.
    """
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    status: OrderStatus
    shop_id: uuid.UUID
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
    customer_note: str | None = None
    accepted_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime
class DeliveryOrderListOut(BaseModel):
    items: list[DeliveryOrderOut]
    total: int
    page: int
    page_size: int
class DeliveryAssignmentOut(BaseModel):
    """One active or past assignment for the current partner."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    order_id: uuid.UUID
    status: DeliveryAssignmentStatus
    accepted_at: datetime | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime
class DeliveryAssignmentListOut(BaseModel):
    items: list[DeliveryAssignmentOut]
    total: int
class LocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    partner_id: uuid.UUID
    order_id: uuid.UUID | None = None
    latitude: Decimal
    longitude: Decimal
    accuracy_m: Decimal | None = None
    created_at: datetime