"""Session cookie helpers.
We store the JWT access token in an httpOnly cookie named "session".
Why a cookie instead of localStorage?
  - httpOnly cookies cannot be read by JavaScript, so XSS can't steal them
  - SameSite=Lax prevents cross-site request forgery on navigation
  - Secure flag ensures the cookie only travels over HTTPS in production
The JWT itself is unchanged — we just deliver it via a cookie instead of
an Authorization header for browser pages. The API (Swagger, mobile
clients) still uses Authorization: Bearer.
"""
from fastapi import Response
from app.core.config import settings
COOKIE_NAME = "session"
REFRESH_COOKIE_NAME = "session_refresh"
# 30 minutes matches ACCESS_TOKEN_EXPIRE_MINUTES
ACCESS_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
_SECURE = settings.ENVIRONMENT == "production"
def set_session_cookies(response: Response, *, access: str, refresh: str) -> None:
    """Attach auth cookies to a response."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=access,
        max_age=ACCESS_COOKIE_MAX_AGE,
        httponly=True,
        secure=_SECURE,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=_SECURE,
        samesite="lax",
        path="/",
    )
def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")