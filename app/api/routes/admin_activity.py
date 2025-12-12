from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from typing import Optional

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.user import User
from app.models.audit import LoginActivity
from app.api.deps.auth import get_current_admin

router = APIRouter()


@router.get("")
async def get_login_activity(
    limit: int = Query(100, le=500),
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get recent login activity."""
    result = await db.execute(
        select(LoginActivity)
        .order_by(LoginActivity.login_time.desc())
        .limit(limit)
    )
    activities = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "user_email": a.user_email,
            "login_time": a.login_time.isoformat() if a.login_time else None,
            "ip_address": a.ip_address,
            "user_agent": a.user_agent,
            "success": a.success,
            "failure_reason": a.failure_reason,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in activities
    ]


@router.get("/stats")
async def get_activity_stats(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get user activity statistics."""
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)
    ninety_days_ago = now - timedelta(days=90)

    # Total users
    total = await db.execute(select(func.count(User.id)))
    total_users = total.scalar() or 0

    # Active in last 7 days
    active_7 = await db.execute(
        select(func.count(User.id))
        .where(User.last_login >= seven_days_ago)
    )
    active_last_7_days = active_7.scalar() or 0

    # Active in last 30 days
    active_30 = await db.execute(
        select(func.count(User.id))
        .where(User.last_login >= thirty_days_ago)
    )
    active_last_30_days = active_30.scalar() or 0

    # Inactive 30+ days
    inactive_30 = await db.execute(
        select(func.count(User.id))
        .where(User.last_login < thirty_days_ago)
        .where(User.last_login >= sixty_days_ago)
    )
    inactive_30_days = inactive_30.scalar() or 0

    # Inactive 60+ days
    inactive_60 = await db.execute(
        select(func.count(User.id))
        .where(User.last_login < sixty_days_ago)
        .where(User.last_login >= ninety_days_ago)
    )
    inactive_60_days = inactive_60.scalar() or 0

    # Inactive 90+ days
    inactive_90 = await db.execute(
        select(func.count(User.id))
        .where(User.last_login < ninety_days_ago)
    )
    inactive_90_days = inactive_90.scalar() or 0

    # Never logged in
    never = await db.execute(
        select(func.count(User.id))
        .where(User.last_login == None)
    )
    never_logged_in = never.scalar() or 0

    return {
        "total_users": total_users,
        "active_last_7_days": active_last_7_days,
        "active_last_30_days": active_last_30_days,
        "inactive_30_days": inactive_30_days,
        "inactive_60_days": inactive_60_days,
        "inactive_90_days": inactive_90_days,
        "never_logged_in": never_logged_in
    }


@router.get("/inactive")
async def get_inactive_users(
    days: int = Query(30, ge=7, le=365),
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get users who haven't logged in for specified days."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(User)
        .where((User.last_login < cutoff) | (User.last_login == None))
        .order_by(User.last_login.asc().nullsfirst())
    )
    users = result.scalars().all()

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_suspended": u.is_suspended
        }
        for u in users
    ]
