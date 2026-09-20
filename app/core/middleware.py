"""Custom middleware.
AuthMiddleware: reads the JWT from the session cookie, loads the User
row, and puts it on request.state.current_user. Never raises — if the
cookie is missing or invalid, current_user is simply None. Pages decide
whether that's OK.
"""
import logging
import uuid
from typing import Callable
from fastapi import Request
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.core.security import TokenError, decode_token
from app.core.session import COOKIE_NAME
from app.db.session import AsyncSessionLocal
from app.models.user import User
logger = logging.getLogger(__name__)
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.current_user = None
        token = request.cookies.get(COOKIE_NAME)
        if token:
            try:
                payload = decode_token(token, expected_type="access")
                user_id = uuid.UUID(payload["sub"])
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(User).where(User.id == user_id))
                    user = result.scalar_one_or_none()
                    if user and user.is_active:
                        request.state.current_user = user
            except (TokenError, ValueError, KeyError):
                pass  # leave as None
            except Exception:
                logger.exception("Auth middleware unexpected error")
        return await call_next(request)