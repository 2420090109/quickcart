"""Cart schemas."""
import uuid
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
class AddCartItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=100)
class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=100)
class CartItemOut(BaseModel):
    """Line in a cart with computed totals."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_slug: str
    product_unit: str
    product_image_url: str | None = None
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    available_qty: int
class CartOut(BaseModel):
    """Full cart with shop info and computed totals."""
    id: uuid.UUID
    shop_id: uuid.UUID
    shop_name: str
    shop_slug: str
    min_order_value: Decimal
    delivery_fee: Decimal
    items: list[CartItemOut]
    subtotal: Decimal
    item_count: int
    meets_min_order: bool
class CartSummary(BaseModel):
    """Lightweight cart summary (for header badges)."""
    id: uuid.UUID | None = None
    shop_id: uuid.UUID | None = None
    item_count: int = 0
    subtotal: Decimal = Decimal("0.00")