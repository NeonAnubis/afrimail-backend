from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.models.admin import AdminUser
from app.models.support import Announcement
from app.api.deps.auth import get_current_admin

router = APIRouter()
public_router = APIRouter()


class AnnouncementCreate(BaseModel):
    title: str
    message: str
    target_group: str = "all"
    priority: str = "normal"
    expires_at: Optional[datetime] = None


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    target_group: Optional[str] = None
    priority: Optional[str] = None
    expires_at: Optional[datetime] = None


@router.get("")
async def get_announcements(
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get all announcements (admin view)."""
    result = await db.execute(
        select(Announcement).order_by(Announcement.created_at.desc())
    )
    announcements = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "title": a.title,
            "message": a.message,
            "target_group": a.target_group,
            "priority": a.priority,
            "published": a.published,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            "created_by": a.created_by,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in announcements
    ]


@router.post("")
async def create_announcement(
    data: AnnouncementCreate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new announcement."""
    announcement = Announcement(
        title=data.title,
        message=data.message,
        target_group=data.target_group,
        priority=data.priority,
        expires_at=data.expires_at,
        created_by=current_admin.email
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)

    return {
        "id": str(announcement.id),
        "title": announcement.title,
        "message": announcement.message,
        "published": announcement.published,
        "created_at": announcement.created_at.isoformat() if announcement.created_at else None
    }


@router.put("/{announcement_id}")
async def update_announcement(
    announcement_id: str,
    data: AnnouncementUpdate,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update an announcement."""
    result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()

    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )

    if data.title is not None:
        announcement.title = data.title
    if data.message is not None:
        announcement.message = data.message
    if data.target_group is not None:
        announcement.target_group = data.target_group
    if data.priority is not None:
        announcement.priority = data.priority
    if data.expires_at is not None:
        announcement.expires_at = data.expires_at

    await db.commit()
    await db.refresh(announcement)

    return {"success": True, "message": "Announcement updated successfully"}


@router.put("/{announcement_id}/publish")
async def publish_announcement(
    announcement_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Publish an announcement."""
    result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()

    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )

    announcement.published = True
    announcement.published_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "Announcement published successfully"}


@router.put("/{announcement_id}/unpublish")
async def unpublish_announcement(
    announcement_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unpublish an announcement."""
    result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()

    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )

    announcement.published = False
    await db.commit()

    return {"success": True, "message": "Announcement unpublished successfully"}


@router.delete("/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete an announcement."""
    result = await db.execute(
        select(Announcement).where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()

    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Announcement not found"
        )

    await db.delete(announcement)
    await db.commit()

    return {"success": True, "message": "Announcement deleted successfully"}


# Public endpoint for users to view announcements
@public_router.get("")
async def get_public_announcements(
    db: AsyncSession = Depends(get_db)
):
    """Get published announcements for users."""
    now = datetime.utcnow()
    result = await db.execute(
        select(Announcement)
        .where(Announcement.published == True)
        .where(
            (Announcement.expires_at == None) | (Announcement.expires_at > now)
        )
        .order_by(Announcement.published_at.desc())
    )
    announcements = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "title": a.title,
            "message": a.message,
            "priority": a.priority,
            "published_at": a.published_at.isoformat() if a.published_at else None
        }
        for a in announcements
    ]
