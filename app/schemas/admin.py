from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class AdminRoleBase(BaseModel):
    """Base admin role schema."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    permissions: Dict[str, Any] = {}


class AdminRoleCreate(AdminRoleBase):
    """Schema for creating an admin role."""
    is_system_role: bool = False


class AdminRoleResponse(AdminRoleBase):
    """Admin role response schema."""
    id: UUID
    is_system_role: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdminUserBase(BaseModel):
    """Base admin user schema."""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)


class AdminUserCreate(AdminUserBase):
    """Schema for creating an admin user."""
    password: str = Field(..., min_length=8)
    role_id: Optional[UUID] = None
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    """Schema for updating an admin user."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=8)
    role_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class AdminUserResponse(BaseModel):
    """Admin user response schema."""
    id: UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    role_id: Optional[UUID] = None
    admin_roles: Optional[AdminRoleResponse] = None

    class Config:
        from_attributes = True


class AdminStatsResponse(BaseModel):
    """Admin dashboard statistics."""
    total_users: int
    active_users: int
    suspended_users: int
    new_users_today: int
    new_users_this_week: int
    total_storage_used: int
    total_storage_allocated: int
    pending_tickets: int
