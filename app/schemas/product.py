"""Product + Category schemas for public browsing."""
import uuid
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
class CategoryOut(BaseModel):
    """Public shape of a category. Hides internal fields like shop_id."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    sort_order: int
class ProductOut(BaseModel):
    """Public shape of a product, including live availability."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    price: Decimal
    mrp: Decimal | None = None
    unit: str
    is_veg: bool | None = None
    category_id: uuid.UUID
    # Populated by the service layer from Inventory, not directly from
    # the Product row. Defaults to 0 if inventory is missing.
    available_qty: int = Field(default=0, description="Units available to order")
    @property
    def discount_percent(self) -> int | None:
        """Derived discount, computed on the fly. Not stored."""
        if self.mrp is None or self.mrp <= self.price:
            return None
        return int(round((1 - (self.price / self.mrp)) * 100))