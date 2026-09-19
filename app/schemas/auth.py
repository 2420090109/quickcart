"""Auth-specific request/response schemas."""
from pydantic import BaseModel, Field
from app.schemas.user import UserOut
class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=1)
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires
class RegisterResponse(BaseModel):
    user: UserOut
    tokens: TokenPair
class RefreshRequest(BaseModel):
    refresh_token: str
class RefreshResponse(BaseModel):
    tokens: TokenPair