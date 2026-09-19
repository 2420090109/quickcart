"""Public shop browsing routes. No auth required."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.product import ProductOut
from app.schemas.shop import (
    NearbyShopOut,
    ShopDetailOut,
    ShopListOut,
    ShopOut,
)
from app.services import shop_service
router = APIRouter(prefix="/shops", tags=["shops"])
@router.get(
    "",
    response_model=ShopListOut,
    summary="List active shops (paginated, filterable)",
)
async def list_shops(
    db: Annotated[AsyncSession, Depends(get_db)],
    city: str | None = Query(None, description="Filter by city (case-insensitive)"),
    is_open: bool | None = Query(None, description="Only open / only closed shops"),
    search: str | None = Query(None, min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ShopListOut:
    items, total = await shop_service.list_shops(
        db,
        city=city,
        is_open=is_open,
        search=search,
        page=page,
        page_size=page_size,
    )
    return ShopListOut(items=items, total=total, page=page, page_size=page_size)
@router.get(
    "/nearby",
    response_model=list[NearbyShopOut],
    summary="Find shops within a radius (Haversine)",
)
async def nearby_shops(
    db: Annotated[AsyncSession, Depends(get_db)],
    lat: float = Query(..., ge=-90, le=90, description="Customer latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Customer longitude"),
    radius_km: float = Query(5.0, gt=0, le=100, description="Search radius in km"),
    limit: int = Query(30, ge=1, le=100),
) -> list[NearbyShopOut]:
    try:
        return await shop_service.nearby_shops(
            db,
            latitude=lat,
            longitude=lng,
            radius_km=radius_km,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
@router.get(
    "/{slug}",
    response_model=ShopDetailOut,
    summary="Get shop detail with categories and products",
)
async def get_shop(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShopDetailOut:
    shop = await shop_service.get_shop_detail(db, slug)
    if shop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop '{slug}' not found.",
        )
    return shop
@router.get(
    "/{slug}/products",
    response_model=list[ProductOut],
    summary="List products in a shop, optionally filtered by category",
)
async def list_shop_products(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    category_slug: str | None = Query(None, description="Filter by category slug"),
) -> list[ProductOut]:
    products = await shop_service.list_shop_products(
        db, slug=slug, category_slug=category_slug
    )
    if products is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shop '{slug}' not found.",
        )
    return products