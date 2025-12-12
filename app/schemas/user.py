from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime, date
from uuid import UUID


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[Literal["male", "female", "non-binary", "prefer-not-to-say"]] = None
    recovery_email: Optional[EmailStr] = None
    recovery_phone: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str = Field(..., min_length=8)
    hcaptcha_token: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[Literal["male", "female", "non-binary", "prefer-not-to-say"]] = None
    recovery_email: Optional[EmailStr] = None
    recovery_phone: Optional[str] = None


class UserResponse(BaseModel):
    """User response schema."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    recovery_email: Optional[str] = None
    recovery_phone: Optional[str] = None
    is_suspended: bool
    last_login: Optional[datetime] = None
    failed_login_attempts: int
    locked_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserInDB(UserResponse):
    """User with password hash (internal use)."""
    password_hash: Optional[str] = None


class MailboxInfoResponse(BaseModel):
    """Mailbox information response."""
    email: str
    quota_bytes: int
    usage_bytes: int
    quota_used_percentage: float

    class Config:
        from_attributes = True
