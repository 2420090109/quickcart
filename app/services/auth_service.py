"""Auth business logic.
This module owns the rules:
  - A phone number must be unique.
  - New accounts default to the requested role only if the requester is
    allowed to create it (for now, only customers can self-register;
    shop_owner / delivery_partner / admin come from seeds or admin API).
  - Login failure is always reported identically (never reveal "user exists
    but wrong password" vs "user does not exist").
"""
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import TokenPair
from app.schemas.user import UserCreate
class AuthError(Exception):
    """Raised on any auth failure. Maps to HTTP 400/401 in the route."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
def _build_token_pair(user: User) -> TokenPair:
    access = create_access_token(str(user.id), user.role.value)
    refresh = create_refresh_token(str(user.id))
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
async def register_user(db: AsyncSession, data: UserCreate) -> tuple[User, TokenPair]:
    """Create a new user + return tokens. Raises AuthError on conflict."""
    # Only customers can self-register. Admin/shop_owner/delivery_partner
    # accounts are created by admins or seed scripts.
    if data.role != UserRole.CUSTOMER:
        raise AuthError(
            "Self-registration is only allowed for customers.", status_code=403
        )
    # Check phone uniqueness
    existing = await db.execute(select(User).where(User.phone == data.phone))
    if existing.scalar_one_or_none():
        raise AuthError("An account with this phone already exists.", status_code=409)
    # Check email uniqueness if provided
    if data.email:
        existing_email = await db.execute(select(User).where(User.email == data.email))
        if existing_email.scalar_one_or_none():
            raise AuthError(
                "An account with this email already exists.", status_code=409
            )
    user = User(
        phone=data.phone,
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=data.role,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, _build_token_pair(user)
async def login_user(db: AsyncSession, phone: str, password: str) -> tuple[User, TokenPair]:
    """Authenticate and return tokens. Never reveals *why* login failed."""
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    # Same error for unknown user vs bad password — no user enumeration.
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid phone or password.", status_code=401)
    if not user.is_active:
        raise AuthError("This account is deactivated.", status_code=403)
    return user, _build_token_pair(user)
async def refresh_tokens(db: AsyncSession, refresh_token: str) -> tuple[User, TokenPair]:
    """Trade a valid refresh token for a new token pair."""
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as e:
        raise AuthError(str(e), status_code=401) from e
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as e:
        raise AuthError("Malformed token subject.", status_code=401) from e
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("User no longer valid.", status_code=401)
    return user, _build_token_pair(user)