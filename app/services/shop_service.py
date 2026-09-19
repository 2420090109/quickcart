"""Shop browsing logic, including Haversine geo search.
Why Haversine in SQL instead of PostGIS?
  - Zero extra setup — works on any Postgres
  - Fast enough up to ~10k shops (which is far beyond our scale)
  - PostGIS is easy to add later: swap the ORDER BY for ST_Distance
Haversine formula (great-circle distance between two lat/lng points):
  a = sin²(Δφ/2) + cos φ1 · cos φ2 · sin²(Δλ/2)
  c = 2 · atan2(√a, √(1−a))
  d = R · c            where R = 6371 km (Earth's mean radius)
In SQL we use the equivalent:
  6371 * acos(
      cos(radians(:lat)) * cos(radians(shop.latitude)) *
      cos(radians(shop.longitude) - radians(:lng)) +
      sin(radians(:lat)) * sin(radians(shop.latitude))
  )
Note: Postgres has `radians()` built-in; no extension needed.
"""
import math
import uuid
from decimal import Decimal
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.category import Category
from app.models.enums import UserRole
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.shop import Shop
from app.schemas.product import CategoryOut, ProductOut
from app.schemas.shop import NearbyShopOut, ShopDetailOut, ShopOut
EARTH_RADIUS_KM = 6371.0
async def list_shops(
    db: AsyncSession,
    *,
    city: str | None = None,
    is_open: bool | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ShopOut], int]:
    """Paginated list of active shops with optional filters."""
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    stmt = select(Shop).where(Shop.is_active.is_(True))
    if city:
        stmt = stmt.where(func.lower(Shop.city) == city.lower())
    if is_open is not None:
        stmt = stmt.where(Shop.is_open.is_(is_open))
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Shop.name).like(pattern),
                func.lower(Shop.description).like(pattern),
            )
        )
    # Count total matches
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    # Apply pagination + ordering
    stmt = stmt.order_by(Shop.name.asc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()
    items = [ShopOut.model_validate(r) for r in rows]
    return items, total
async def nearby_shops(
    db: AsyncSession,
    *,
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    limit: int = 30,
) -> list[NearbyShopOut]:
    """Find shops within `radius_km` of (latitude, longitude).
    Uses the Haversine formula directly in SQL. Returns shops sorted by
    ascending distance, each with a computed `distance_km`.
    """
    # Sanity-check inputs
    if not (-90 <= latitude <= 90):
        raise ValueError("latitude must be between -90 and 90")
    if not (-180 <= longitude <= 180):
        raise ValueError("longitude must be between -180 and 180")
    if radius_km <= 0 or radius_km > 100:
        raise ValueError("radius_km must be between 0 and 100")
    limit = min(max(1, limit), 100)
    # Haversine SQL expression, using the *database's* latitude/longitude
    # columns and the query point parameters.
    # `func.acos` maps to Postgres's `acos()`. `func.radians` -> `radians()`.
    distance_expr = (
        EARTH_RADIUS_KM
        * func.acos(
            func.cos(func.radians(latitude))
            * func.cos(func.radians(Shop.latitude))
            * func.cos(func.radians(Shop.longitude) - func.radians(longitude))
            + func.sin(func.radians(latitude))
            * func.sin(func.radians(Shop.latitude))
        )
    ).label("distance_km")
    stmt = (
        select(Shop, distance_expr)
        .where(Shop.is_active.is_(True))
        # Pre-filter with a bounding box for performance.
        # Every degree of latitude is ~111 km. Longitude compresses with
        # latitude, so we divide by cos(latitude) to keep the box generous.
        .where(Shop.latitude.between(latitude - radius_km / 111.0, latitude + radius_km / 111.0))
        .where(
            Shop.longitude.between(
                longitude - radius_km / (111.0 * max(math.cos(math.radians(latitude)), 0.01)),
                longitude + radius_km / (111.0 * max(math.cos(math.radians(latitude)), 0.01)),
            )
        )
        # Then filter to actual circle, not the box
        .where(distance_expr <= radius_km)
        .order_by(distance_expr.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    result: list[NearbyShopOut] = []
    for shop, distance in rows:
        base = ShopOut.model_validate(shop).model_dump()
        result.append(NearbyShopOut(**base, distance_km=round(float(distance), 3)))
    return result
async def get_shop_detail(db: AsyncSession, slug: str) -> ShopDetailOut | None:
    """Return a shop with all its categories and products, or None."""
    stmt = (
        select(Shop)
        .where(Shop.slug == slug, Shop.is_active.is_(True))
        .options(selectinload(Shop.categories), selectinload(Shop.products))
    )
    shop = (await db.execute(stmt)).scalar_one_or_none()
    if shop is None:
        return None
    # Build a lookup of product_id -> available_qty from inventory
    product_ids = [p.id for p in shop.products]
    avail_map: dict[uuid.UUID, int] = {}
    if product_ids:
        inv_stmt = select(Inventory).where(Inventory.product_id.in_(product_ids))
        inventories = (await db.execute(inv_stmt)).scalars().all()
        avail_map = {inv.product_id: inv.available_qty for inv in inventories}
    # Only active products
    active_products = [p for p in shop.products if p.is_active]
    active_categories = sorted(
        [c for c in shop.categories if c.is_active],
        key=lambda c: (c.sort_order, c.name),
    )
    products_out = [
        ProductOut(
            id=p.id,
            name=p.name,
            slug=p.slug,
            description=p.description,
            image_url=p.image_url,
            price=p.price,
            mrp=p.mrp,
            unit=p.unit,
            is_veg=p.is_veg,
            category_id=p.category_id,
            available_qty=avail_map.get(p.id, 0),
        )
        for p in sorted(active_products, key=lambda p: p.name)
    ]
    categories_out = [CategoryOut.model_validate(c) for c in active_categories]
    base = ShopOut.model_validate(shop).model_dump()
    return ShopDetailOut(
        **base,
        address_line=shop.address_line,
        phone=shop.phone,
        categories=categories_out,
        products=products_out,
    )
async def list_shop_products(
    db: AsyncSession,
    *,
    slug: str,
    category_slug: str | None = None,
) -> list[ProductOut] | None:
    """List active products in a shop, optionally filtered by category slug."""
    shop_stmt = select(Shop).where(Shop.slug == slug, Shop.is_active.is_(True))
    shop = (await db.execute(shop_stmt)).scalar_one_or_none()
    if shop is None:
        return None
    stmt = select(Product).where(Product.shop_id == shop.id, Product.is_active.is_(True))
    if category_slug:
        cat_stmt = select(Category).where(
            Category.shop_id == shop.id, Category.slug == category_slug
        )
        category = (await db.execute(cat_stmt)).scalar_one_or_none()
        if category is None:
            return []
        stmt = stmt.where(Product.category_id == category.id)
    stmt = stmt.order_by(Product.name.asc())
    products = (await db.execute(stmt)).scalars().all()
    # Attach availability
    product_ids = [p.id for p in products]
    avail_map: dict[uuid.UUID, int] = {}
    if product_ids:
        inv_stmt = select(Inventory).where(Inventory.product_id.in_(product_ids))
        inventories = (await db.execute(inv_stmt)).scalars().all()
        avail_map = {inv.product_id: inv.available_qty for inv in inventories}
    return [
        ProductOut(
            id=p.id,
            name=p.name,
            slug=p.slug,
            description=p.description,
            image_url=p.image_url,
            price=p.price,
            mrp=p.mrp,
            unit=p.unit,
            is_veg=p.is_veg,
            category_id=p.category_id,
            available_qty=avail_map.get(p.id, 0),
        )
        for p in products
    ]