from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.user import User
from app.models.sending import (
    SendingTier, EmailSendingLimit, SendingLimitViolation
)
from app.api.deps.auth import get_current_admin

router = APIRouter()


class LimitUpdate(BaseModel):
    tier_name: Optional[str] = None
    daily_limit: Optional[int] = None
    hourly_limit: Optional[int] = None
    is_sending_enabled: Optional[bool] = None
    custom_limit_reason: Optional[str] = None


@router.get("/stats")
async def get_sending_stats(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get sending limits statistics."""
    # Total sent today
    total_sent = await db.execute(
        select(func.sum(EmailSendingLimit.emails_sent_today))
    )
    total_sent_today = total_sent.scalar() or 0

    # Users at limit
    at_limit = await db.execute(
        select(func.count(EmailSendingLimit.id))
        .where(EmailSendingLimit.emails_sent_today >= EmailSendingLimit.daily_limit)
    )
    users_at_limit = at_limit.scalar() or 0

    # Users near limit (>80%)
    near_limit = await db.execute(
        select(func.count(EmailSendingLimit.id))
        .where(EmailSendingLimit.emails_sent_today >= EmailSendingLimit.daily_limit * 0.8)
        .where(EmailSendingLimit.emails_sent_today < EmailSendingLimit.daily_limit)
    )
    users_near_limit = near_limit.scalar() or 0

    # Active violations
    violations = await db.execute(
        select(func.count(SendingLimitViolation.id))
        .where(SendingLimitViolation.is_resolved == False)
    )
    active_violations = violations.scalar() or 0

    # Total users with limits
    total = await db.execute(
        select(func.count(EmailSendingLimit.id))
    )
    total_users = total.scalar() or 0

    # Free tier users (revenue opportunity)
    free_tier = await db.execute(
        select(func.count(EmailSendingLimit.id))
        .where(EmailSendingLimit.tier_name == "free")
    )
    revenue_opportunity = free_tier.scalar() or 0

    return {
        "total_sent_today": total_sent_today,
        "users_at_limit": users_at_limit,
        "users_near_limit": users_near_limit,
        "active_violations": active_violations,
        "total_users": total_users,
        "revenue_opportunity_count": revenue_opportunity
    }


@router.get("/users")
async def get_sending_limits(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all users' sending limits."""
    result = await db.execute(
        select(EmailSendingLimit, User)
        .outerjoin(User, EmailSendingLimit.user_id == User.id)
        .order_by(EmailSendingLimit.emails_sent_today.desc())
    )
    limits = result.all()

    return [
        {
            "id": str(l.EmailSendingLimit.id),
            "user_id": str(l.EmailSendingLimit.user_id),
            "email": l.User.email if l.User else None,
            "name": f"{l.User.first_name} {l.User.last_name}" if l.User else None,
            "tier_id": str(l.EmailSendingLimit.tier_id) if l.EmailSendingLimit.tier_id else None,
            "tier_name": l.EmailSendingLimit.tier_name,
            "daily_limit": l.EmailSendingLimit.daily_limit,
            "hourly_limit": l.EmailSendingLimit.hourly_limit,
            "emails_sent_today": l.EmailSendingLimit.emails_sent_today,
            "emails_sent_this_hour": l.EmailSendingLimit.emails_sent_this_hour,
            "usage_percent": (l.EmailSendingLimit.emails_sent_today / l.EmailSendingLimit.daily_limit * 100) if l.EmailSendingLimit.daily_limit > 0 else 0,
            "last_reset_date": str(l.EmailSendingLimit.last_reset_date) if l.EmailSendingLimit.last_reset_date else None,
            "last_reset_hour": l.EmailSendingLimit.last_reset_hour.isoformat() if l.EmailSendingLimit.last_reset_hour else None,
            "is_sending_enabled": l.EmailSendingLimit.is_sending_enabled,
            "custom_limit_reason": l.EmailSendingLimit.custom_limit_reason,
            "created_at": l.EmailSendingLimit.created_at.isoformat() if l.EmailSendingLimit.created_at else None,
            "updated_at": l.EmailSendingLimit.updated_at.isoformat() if l.EmailSendingLimit.updated_at else None
        }
        for l in limits
    ]


@router.put("/{limit_id}")
async def update_sending_limit(
    limit_id: str,
    data: LimitUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a user's sending limits."""
    result = await db.execute(
        select(EmailSendingLimit).where(EmailSendingLimit.id == limit_id)
    )
    limit = result.scalar_one_or_none()

    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sending limit not found"
        )

    if data.tier_name is not None:
        limit.tier_name = data.tier_name
    if data.daily_limit is not None:
        limit.daily_limit = data.daily_limit
    if data.hourly_limit is not None:
        limit.hourly_limit = data.hourly_limit
    if data.is_sending_enabled is not None:
        limit.is_sending_enabled = data.is_sending_enabled
    if data.custom_limit_reason is not None:
        limit.custom_limit_reason = data.custom_limit_reason

    await db.commit()
    await db.refresh(limit)

    return {"success": True, "message": "Sending limit updated"}


@router.put("/{limit_id}/unblock")
async def unblock_user(
    limit_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unblock a user's sending."""
    result = await db.execute(
        select(EmailSendingLimit).where(EmailSendingLimit.id == limit_id)
    )
    limit = result.scalar_one_or_none()

    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sending limit not found"
        )

    limit.is_sending_enabled = True
    limit.custom_limit_reason = None
    await db.commit()

    return {"success": True, "message": "User unblocked"}


@router.get("/violations")
async def get_violations(
    resolved: Optional[bool] = None,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get sending limit violations."""
    query = select(SendingLimitViolation, User).outerjoin(
        User, SendingLimitViolation.user_id == User.id
    ).order_by(SendingLimitViolation.created_at.desc())

    if resolved is not None:
        query = query.where(SendingLimitViolation.is_resolved == resolved)

    result = await db.execute(query)
    violations = result.all()

    return [
        {
            "id": str(v.SendingLimitViolation.id),
            "user_id": str(v.SendingLimitViolation.user_id),
            "email": v.User.email if v.User else None,
            "name": f"{v.User.first_name} {v.User.last_name}" if v.User else None,
            "violation_type": v.SendingLimitViolation.violation_type,
            "attempted_count": v.SendingLimitViolation.attempted_count,
            "limit_at_time": v.SendingLimitViolation.limit_at_time,
            "violation_details": v.SendingLimitViolation.violation_details,
            "action_taken": v.SendingLimitViolation.action_taken,
            "admin_notes": v.SendingLimitViolation.admin_notes,
            "is_resolved": v.SendingLimitViolation.is_resolved,
            "resolved_at": v.SendingLimitViolation.resolved_at.isoformat() if v.SendingLimitViolation.resolved_at else None,
            "resolved_by": v.SendingLimitViolation.resolved_by,
            "created_at": v.SendingLimitViolation.created_at.isoformat() if v.SendingLimitViolation.created_at else None
        }
        for v in violations
    ]


@router.put("/violations/{violation_id}/resolve")
async def resolve_violation(
    violation_id: str,
    admin_notes: str = "",
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Resolve a violation."""
    from datetime import datetime

    result = await db.execute(
        select(SendingLimitViolation).where(SendingLimitViolation.id == violation_id)
    )
    violation = result.scalar_one_or_none()

    if not violation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found"
        )

    violation.is_resolved = True
    violation.resolved_at = datetime.utcnow()
    violation.resolved_by = current_admin.email
    violation.admin_notes = admin_notes

    await db.commit()

    return {"success": True, "message": "Violation resolved"}


@router.post("/users/{user_id}/reset")
async def reset_user_sending_limit(
    user_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Reset a user's sending counts."""
    result = await db.execute(
        select(EmailSendingLimit).where(EmailSendingLimit.user_id == user_id)
    )
    limit = result.scalar_one_or_none()

    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sending limit not found"
        )

    limit.emails_sent_today = 0
    limit.emails_sent_this_hour = 0
    await db.commit()

    return {"success": True, "message": "Sending counts reset"}


class SuspendSendingRequest(BaseModel):
    reason: str = ""


@router.post("/users/{user_id}/suspend-sending")
async def suspend_user_sending(
    user_id: str,
    data: SuspendSendingRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend a user's sending privileges."""
    result = await db.execute(
        select(EmailSendingLimit).where(EmailSendingLimit.user_id == user_id)
    )
    limit = result.scalar_one_or_none()

    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sending limit not found"
        )

    limit.is_sending_enabled = False
    limit.custom_limit_reason = data.reason
    await db.commit()

    return {"success": True, "message": "Sending suspended"}


@router.post("/users/{user_id}/resume-sending")
async def resume_user_sending(
    user_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Resume a user's sending privileges."""
    result = await db.execute(
        select(EmailSendingLimit).where(EmailSendingLimit.user_id == user_id)
    )
    limit = result.scalar_one_or_none()

    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sending limit not found"
        )

    limit.is_sending_enabled = True
    limit.custom_limit_reason = None
    await db.commit()

    return {"success": True, "message": "Sending resumed"}


class UpdateLimitRequest(BaseModel):
    daily_limit: Optional[int] = None
    hourly_limit: Optional[int] = None


@router.put("/users/{user_id}/limit")
async def update_user_sending_limit(
    user_id: str,
    data: UpdateLimitRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a user's sending limits."""
    result = await db.execute(
        select(EmailSendingLimit).where(EmailSendingLimit.user_id == user_id)
    )
    limit = result.scalar_one_or_none()

    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sending limit not found"
        )

    if data.daily_limit is not None:
        limit.daily_limit = data.daily_limit
    if data.hourly_limit is not None:
        limit.hourly_limit = data.hourly_limit

    await db.commit()

    return {"success": True, "message": "Limits updated"}
