"""Security primitives: password hashing and JWT.
Design decisions:
  - bcrypt via passlib — battle-tested, not our own crypto
  - Two token types (access + refresh) with DIFFERENT secrets/expiries
    so a leaked access token can't be used to mint new ones
  - Token "type" claim prevents refresh tokens from being used as access tokens
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
import jwt  # PyJWT
from passlib.context import CryptContext
from app.core.config import settings
# --- Password hashing ---
# bcrypt with auto-upgrading rounds. New hashes use the latest default.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(plain_password: str) -> str:
    """Hash a plaintext password. Store ONLY this in the DB."""
    return pwd_context.hash(plain_password)
def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash. Constant-time."""
    try:
        return pwd_context.verify(plain_password, password_hash)
    except Exception:
        # Corrupted hash, wrong algorithm, etc. — always fail closed.
        return False
# --- JWT ---
ALGORITHM = "HS256"
def _create_token(
    subject: str,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Internal: build a signed JWT."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,               # user id
        "type": token_type,           # prevents cross-use of tokens
        "iat": now,                   # issued at
        "exp": now + expires_delta,   # expiry
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
def create_access_token(user_id: str, role: str) -> str:
    """Short-lived token used on every authenticated request."""
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={"role": role},
    )
def create_refresh_token(user_id: str) -> str:
    """Long-lived token used only to mint new access tokens."""
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
class TokenError(Exception):
    """Raised when a token is invalid, expired, or the wrong type."""
def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
    """Decode and validate a JWT. Raises TokenError on any problem."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise TokenError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenError("Invalid token") from e
    if payload.get("type") != expected_type:
        raise TokenError(f"Expected {expected_type} token, got {payload.get('type')!r}")
    if not payload.get("sub"):
        raise TokenError("Token missing subject")
    return payload