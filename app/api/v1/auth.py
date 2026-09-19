"""Auth routes: register, login, refresh, me."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import CurrentUser
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterResponse,
)
from app.schemas.user import UserCreate, UserOut
from app.services.auth_service import (
    AuthError,
    login_user,
    refresh_tokens,
    register_user,
)
router = APIRouter(prefix="/auth", tags=["auth"])
@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer account",
)
async def register(
    data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponse:
    """Register a new customer. Returns the user and a fresh token pair.
    Only customers can self-register; shop owners and delivery partners
    are created by admins or seeds.
    """
    try:
        user, tokens = await register_user(db, data)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return RegisterResponse(user=UserOut.model_validate(user), tokens=tokens)
@router.post(
    "/login",
    response_model=RegisterResponse,
    summary="Login with phone + password",
)
async def login(
    data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponse:
    """Authenticate and receive a fresh token pair."""
    try:
        user, tokens = await login_user(db, data.phone, data.password)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return RegisterResponse(user=UserOut.model_validate(user), tokens=tokens)
@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Trade a refresh token for a new token pair",
)
async def refresh(
    data: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RefreshResponse:
    try:
        _, tokens = await refresh_tokens(db, data.refresh_token)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return RefreshResponse(tokens=tokens)
@router.get(
    "/me",
    response_model=UserOut,
    summary="Return the current authenticated user",
)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)