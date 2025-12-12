from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.mailbox import MailboxMetadata
from app.models.settings import SystemSettings
from app.api.deps.auth import get_current_admin

router = APIRouter()


@router.get("")
async def get_storage_overview(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get storage overview for all users."""
    result = await db.execute(
        select(MailboxMetadata).order_by(MailboxMetadata.usage_bytes.desc())
    )
    mailboxes = result.scalars().all()

    return [
        {
            "email": m.email,
            "quota_bytes": m.quota_bytes,
            "usage_bytes": m.usage_bytes,
            "usage_percent": (m.usage_bytes / m.quota_bytes * 100) if m.quota_bytes > 0 else 0,
            "last_synced": m.last_synced.isoformat() if m.last_synced else None
        }
        for m in mailboxes
    ]


@router.get("/stats")
async def get_storage_stats(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get storage statistics."""
    try:
        # Get all mailboxes for calculation
        result = await db.execute(select(MailboxMetadata))
        mailboxes = result.scalars().all()

        # Calculate stats from results
        total_allocated = sum(m.quota_bytes or 0 for m in mailboxes)
        total_used = sum(m.usage_bytes or 0 for m in mailboxes)

        # Calculate average usage percent
        usage_percents = [
            (m.usage_bytes / m.quota_bytes * 100) if m.quota_bytes and m.quota_bytes > 0 else 0
            for m in mailboxes
        ]
        average_usage_percent = sum(usage_percents) / len(usage_percents) if usage_percents else 0

        # Users over 90%
        users_over_90_percent = sum(
            1 for m in mailboxes
            if m.quota_bytes and m.quota_bytes > 0 and m.usage_bytes >= m.quota_bytes * 0.9
        )

        # Top users by usage (sort and take top 10)
        sorted_mailboxes = sorted(mailboxes, key=lambda m: m.usage_bytes or 0, reverse=True)[:10]
        top_users = [
            {
                "email": m.email,
                "usage_bytes": m.usage_bytes or 0,
                "quota_bytes": m.quota_bytes or 0,
                "usage_percent": (m.usage_bytes / m.quota_bytes * 100) if m.quota_bytes and m.quota_bytes > 0 else 0
            }
            for m in sorted_mailboxes
        ]

        return {
            "total_allocated": total_allocated,
            "total_used": total_used,
            "average_usage_percent": average_usage_percent,
            "users_over_90_percent": users_over_90_percent,
            "top_users": top_users
        }
    except Exception as e:
        # Return empty stats if there's an error (e.g., table doesn't exist yet)
        return {
            "total_allocated": 0,
            "total_used": 0,
            "average_usage_percent": 0,
            "users_over_90_percent": 0,
            "top_users": []
        }


@router.get("/presets")
async def get_quota_presets(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get quota presets."""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.setting_key == "quota_presets")
    )
    setting = result.scalar_one_or_none()

    if setting and setting.setting_value:
        return setting.setting_value.get("presets", [])

    # Default presets
    return [
        {"name": "Basic", "value": 1073741824},  # 1GB
        {"name": "Standard", "value": 5368709120},  # 5GB
        {"name": "Premium", "value": 10737418240},  # 10GB
        {"name": "Business", "value": 26843545600}  # 25GB
    ]
