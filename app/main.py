"""FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.api.v1 import api_router
from app.api.v1.auth_pages import router as auth_pages_router
from app.api.v1.cart_pages import router as cart_pages_router
from app.api.v1.checkout_pages import router as checkout_pages_router
from app.api.v1.delivery_pages import router as delivery_pages_router
from app.api.v1.order_pages import router as order_pages_router
from app.api.v1.pages import router as pages_router
from app.api.v1.payment_pages import router as payment_pages_router
from app.api.v1.shop_owner_pages import router as shop_owner_pages_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import AuthMiddleware
from app.core.templating import templates
from app.db.session import engine, redis_client
setup_logging()
logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s [%s]", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)
    await engine.dispose()
    await redis_client.aclose()
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)
# --- Static files ---
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
# app/main.py -> app/ -> static
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info("Mounted static files from %s", STATIC_DIR)
# --- Routers ---
app.include_router(api_router, prefix="/api/v1")
app.include_router(pages_router)
app.include_router(auth_pages_router)
app.include_router(cart_pages_router)
app.include_router(checkout_pages_router)
app.include_router(order_pages_router)
app.include_router(payment_pages_router)
app.include_router(shop_owner_pages_router)
app.include_router(delivery_pages_router)
# --- Friendly error pages (only for HTML routes; API still gets JSON) ---
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/") or request.url.path.startswith("/static/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "current_user": getattr(request.state, "current_user", None),
            "code": 404,
            "message": "We couldn't find that page. It may have moved or never existed.",
        },
        status_code=404,
    )
@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.exception("Unhandled error at %s", request.url.path)
    if request.url.path.startswith("/api/") or request.url.path.startswith("/static/"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "current_user": getattr(request.state, "current_user", None),
            "code": 500,
            "message": "Something went wrong on our side. We're looking into it.",
        },
        status_code=500,
    )