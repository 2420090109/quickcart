"""FastAPI dependencies — shared across all routers.
The two big ones:
  - get_current_user: decodes the Bearer JWT and returns the User row.
    Raises 401 on any failure (missing header, bad signature, expired,
    wrong token type).
  - require_role(...): factory that returns a dependency enforcing
    role-based access. Use like:
        @router.post("/shops", dependencies=[Depends(require_role(UserRole.SHOP_OWNER))])
    or grab the user inline:
        async def create_shop(
            user: User = Depends(require_role(UserRole.SHOP_OWNER)),
        ): ...
"""
import uuid
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
# `auto_error=False` means we handle the "no header" case ourselves so
# we can return a consistent 401 message instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)
async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from the Authorization header."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token subject.",
        ) from e
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    return user
def require_role(*allowed_roles: UserRole):
    """Dependency factory: allow only the given roles.
    Usage:
        @router.get("/admin-only")
        async def x(user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    """
    async def _checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This endpoint requires one of: "
                    f"{', '.join(r.value for r in allowed_roles)}."
                ),
            )
        return user
    return _checker
# Convenience type aliases for route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]