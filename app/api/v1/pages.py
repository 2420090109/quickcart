"""HTML page routes (server-rendered via Jinja2)."""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.templating import templates
from app.db.session import get_db
from app.services import shop_service
logger = logging.getLogger(__name__)
router = APIRouter(tags=["pages"])
def _ctx(request: Request, **extra):
    return {
        "request": request,
        "current_user": getattr(request.state, "current_user", None),
        **extra,
    }
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> HTMLResponse:
    return templates.TemplateResponse("home.html", _ctx(request))
@router.get("/shops", response_class=HTMLResponse, include_in_schema=False)
async def shops_list(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    city: str | None = Query(None),
    format: str | None = Query(None),
) -> HTMLResponse:
    city = (city or "").strip() or None
    items, _total = await shop_service.list_shops(
        db, city=city, is_open=None, page=1, page_size=50
    )
    # HTMX partial request — return just the grid
    if format == "html" or request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "shops/_grid.html", _ctx(request, shops=items)
        )
    return templates.TemplateResponse(
        "shops/list.html", _ctx(request, shops=items)
    )
@router.get("/shops/nearby", response_class=HTMLResponse, include_in_schema=False)
async def shops_nearby(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    lat: float = Query(12.9352),
    lng: float = Query(77.6245),
    radius: float = Query(5.0),
) -> HTMLResponse:
    try:
        items = await shop_service.nearby_shops(
            db, latitude=lat, longitude=lng, radius_km=radius, limit=50
        )
    except ValueError:
        items = []
    return templates.TemplateResponse("shops/_grid.html", _ctx(request, shops=items))
@router.get("/shops/{slug}", response_class=HTMLResponse, include_in_schema=False)
async def shop_detail(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    shop = await shop_service.get_shop_detail(db, slug)
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    return templates.TemplateResponse(
        "shops/detail.html",
        _ctx(request, shop=shop, products=shop.products),
    )
@router.get("/shops/{slug}/products", response_class=HTMLResponse, include_in_schema=False)
async def shop_products_partial(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    category_slug: str | None = Query(None),
) -> HTMLResponse:
    products = await shop_service.list_shop_products(
        db, slug=slug, category_slug=category_slug
    )
    if products is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    return templates.TemplateResponse(
        "shops/_product_grid.html", _ctx(request, products=products)
    )