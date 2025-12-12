from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.db.session import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.admin import AdminUser, AdminRole
from app.models.user import User
from app.models.mailbox import MailboxMetadata
from app.models.support import SupportTicket
from app.models.audit import AuditLog
from app.schemas.auth import AdminLoginRequest, TokenResponse
from app.schemas.admin import (
    AdminUserCreate, AdminUserUpdate, AdminUserResponse,
    AdminRoleCreate, AdminRoleResponse, AdminStatsResponse
)
from app.api.deps.auth import get_current_admin

router = APIRouter()
admins_router = APIRouter()
roles_router = APIRouter()
stats_router = APIRouter()


@router.get("/auth/me")
async def get_admin_me(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get current authenticated admin info."""
    return {
        "user": {
            "id": str(current_admin.id),
            "email": current_admin.email,
            "name": current_admin.name,
            "is_active": current_admin.is_active,
            "role_id": str(current_admin.role_id) if current_admin.role_id else None,
            "last_login": current_admin.last_login.isoformat() if current_admin.last_login else None,
            "created_at": current_admin.created_at.isoformat() if current_admin.created_at else None
        },
        "isAdmin": True
    }


@router.post("/auth/login", response_model=TokenResponse)
async def admin_login(
    request: Request,
    data: AdminLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Admin login endpoint."""
    # Get admin
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == data.email.lower())
    )
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is inactive"
        )

    # Verify password
    if not verify_password(data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Update last login
    admin.last_login = datetime.utcnow()
    await db.commit()

    # Generate token
    token = create_access_token(data={"sub": admin.email}, is_admin=True)

    return TokenResponse(
        success=True,
        token=token,
        user={
            "id": str(admin.id),
            "email": admin.email,
            "name": admin.name,
            "is_admin": True
        }
    )


@stats_router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get admin dashboard statistics."""
    # Total users
    total_result = await db.execute(select(func.count(User.id)))
    total_users = total_result.scalar() or 0

    # Active users (not suspended)
    active_result = await db.execute(
        select(func.count(User.id)).where(User.is_suspended == False)
    )
    active_users = active_result.scalar() or 0

    # Suspended users
    suspended_users = total_users - active_users

    # New users today
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    new_today_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= today_start)
    )
    new_users_today = new_today_result.scalar() or 0

    # New users this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    new_week_result = await db.execute(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )
    new_users_this_week = new_week_result.scalar() or 0

    # Storage stats
    storage_result = await db.execute(
        select(
            func.coalesce(func.sum(MailboxMetadata.usage_bytes), 0),
            func.coalesce(func.sum(MailboxMetadata.quota_bytes), 0)
        )
    )
    storage_row = storage_result.first()
    total_storage_used = storage_row[0] if storage_row else 0
    total_storage_allocated = storage_row[1] if storage_row else 0

    # Pending support tickets
    pending_result = await db.execute(
        select(func.count(SupportTicket.id))
        .where(SupportTicket.status == "pending")
    )
    pending_tickets = pending_result.scalar() or 0

    return AdminStatsResponse(
        total_users=total_users,
        active_users=active_users,
        suspended_users=suspended_users,
        new_users_today=new_users_today,
        new_users_this_week=new_users_this_week,
        total_storage_used=total_storage_used,
        total_storage_allocated=total_storage_allocated,
        pending_tickets=pending_tickets
    )


# Admin Users Management
@admins_router.get("")
async def get_admins(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all admin users."""
    result = await db.execute(
        select(AdminUser).order_by(AdminUser.created_at.desc())
    )
    admins = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "email": a.email,
            "name": a.name,
            "is_active": a.is_active,
            "role_id": str(a.role_id) if a.role_id else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "last_login": a.last_login.isoformat() if a.last_login else None
        }
        for a in admins
    ]


@admins_router.post("")
async def create_admin(
    data: AdminUserCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new admin user."""
    # Check if email already exists
    existing = await db.execute(
        select(AdminUser).where(AdminUser.email == data.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this email already exists"
        )

    admin = AdminUser(
        email=data.email.lower(),
        name=data.name,
        password_hash=get_password_hash(data.password),
        role_id=data.role_id,
        is_active=data.is_active,
        created_by=current_admin.id
    )
    db.add(admin)

    # Log action
    log = AuditLog(
        action_type="admin_created",
        admin_email=current_admin.email,
        target_user_email=data.email,
        details={"name": data.name}
    )
    db.add(log)

    await db.commit()
    await db.refresh(admin)

    return {
        "success": True,
        "message": "Admin created successfully",
        "admin": {
            "id": str(admin.id),
            "email": admin.email,
            "name": admin.name
        }
    }


@admins_router.put("/{admin_id}")
async def update_admin(
    admin_id: str,
    data: AdminUserUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update an admin user."""
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == admin_id)
    )
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )

    if data.name is not None:
        admin.name = data.name
    if data.password is not None:
        admin.password_hash = get_password_hash(data.password)
    if data.role_id is not None:
        admin.role_id = data.role_id
    if data.is_active is not None:
        admin.is_active = data.is_active

    await db.commit()
    await db.refresh(admin)

    return {"success": True, "message": "Admin updated successfully"}


@admins_router.delete("/{admin_id}")
async def delete_admin(
    admin_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete an admin user."""
    if str(current_admin.id) == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    result = await db.execute(
        select(AdminUser).where(AdminUser.id == admin_id)
    )
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )

    await db.delete(admin)
    await db.commit()

    return {"success": True, "message": "Admin deleted successfully"}


from pydantic import BaseModel as PydanticBaseModel


class AdminToggleRequest(PydanticBaseModel):
    is_active: bool


@admins_router.put("/{admin_id}/toggle")
async def toggle_admin_active(
    admin_id: str,
    data: AdminToggleRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle admin user active status."""
    if str(current_admin.id) == admin_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own active status"
        )

    result = await db.execute(
        select(AdminUser).where(AdminUser.id == admin_id)
    )
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found"
        )

    admin.is_active = data.is_active
    await db.commit()

    return {
        "success": True,
        "message": f"Admin {'activated' if data.is_active else 'deactivated'} successfully"
    }


# Roles Management
@roles_router.get("")
async def get_roles(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all admin roles."""
    result = await db.execute(
        select(AdminRole).order_by(AdminRole.name)
    )
    roles = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "permissions": r.permissions,
            "is_system_role": r.is_system_role,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in roles
    ]


@roles_router.post("")
async def create_role(
    data: AdminRoleCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new admin role."""
    role = AdminRole(
        name=data.name,
        description=data.description,
        permissions=data.permissions,
        is_system_role=False
    )
    db.add(role)
    await db.commit()
    await db.refresh(role)

    return {
        "success": True,
        "message": "Role created successfully",
        "role": {
            "id": str(role.id),
            "name": role.name
        }
    }
