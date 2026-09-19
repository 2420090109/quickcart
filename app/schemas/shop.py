"""Shop schemas for public browsing."""
import uuid
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.schemas.product import CategoryOut, ProductOut
class ShopOut(BaseModel):
    """Public summary of a shop — what shows on the browse list."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    city: str
    pincode: str
    latitude: Decimal
    longitude: Decimal
    is_open: bool
    delivery_radius_km: Decimal
    min_order_value: Decimal
    delivery_fee: Decimal
    avg_prep_minutes: int
class NearbyShopOut(ShopOut):
    """ShopOut plus the computed distance from the query point."""
    distance_km: float
class ShopDetailOut(ShopOut):
    """ShopOut plus its full catalog for the shop detail page."""
    address_line: str
    phone: str
    categories: list[CategoryOut]
    products: list[ProductOut]
class ShopListOut(BaseModel):
    """Paginated list of shops."""
    items: list[ShopOut]
    total: int
    page: int
    page_size: int