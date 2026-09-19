"""Pydantic schemas for User — request/response shapes."""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.enums import UserRole
class UserBase(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    email: EmailStr | None = None
    full_name: str = Field(..., min_length=2, max_length=120)
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.CUSTOMER
class UserOut(UserBase):
    """What we return to clients. Never includes password_hash."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime