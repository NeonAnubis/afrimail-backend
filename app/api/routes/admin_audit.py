from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.audit import AuditLog
from app.api.deps.auth import get_current_admin

router = APIRouter()


@router.get("")
async def get_audit_logs(
    action_type: Optional[str] = None,
    admin_email: Optional[str] = None,
    target_email: Optional[str] = None,
    limit: int = Query(100, le=500),
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get audit logs with optional filtering."""
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())

    if action_type:
        query = query.where(AuditLog.action_type == action_type)
    if admin_email:
        query = query.where(AuditLog.admin_email == admin_email)
    if target_email:
        query = query.where(AuditLog.target_user_email == target_email)

    query = query.limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": str(l.id),
            "action_type": l.action_type,
            "admin_email": l.admin_email,
            "target_user_email": l.target_user_email,
            "details": l.details,
            "ip_address": l.ip_address,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None
        }
        for l in logs
    ]
