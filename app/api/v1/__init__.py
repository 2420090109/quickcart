"""API v1 routers."""
from fastapi import APIRouter
from app.api.v1 import (
    auth,
    cart,
    delivery,
    health,
    orders,
    payments,
    shop_owner,
    shops,
    webhooks,
)
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(shops.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
api_router.include_router(shop_owner.router)
api_router.include_router(delivery.router)
api_router.include_router(webhooks.router)
__all__ = ["api_router"]