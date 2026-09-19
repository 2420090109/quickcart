import logging
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, redis_client
logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])
@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    db_status = "ok"
    redis_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("DB health check failed")
        db_status = f"error: {exc.__class__.__name__}"
    try:
        await redis_client.ping()
    except Exception as exc:
        logger.exception("Redis health check failed")
        redis_status = f"error: {exc.__class__.__name__}"
    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "redis": redis_status,
    }